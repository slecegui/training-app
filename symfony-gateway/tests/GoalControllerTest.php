<?php

namespace App\Tests;

use App\Controller\GoalController;
use App\Service\PythonSessionClient;
use PHPUnit\Framework\TestCase;
use Psr\Log\NullLogger;
use Symfony\Component\HttpClient\Exception\TransportException;
use Symfony\Component\HttpClient\MockHttpClient;
use Symfony\Component\HttpClient\Response\MockResponse;
use Symfony\Component\HttpFoundation\Request;

final class GoalControllerTest extends TestCase
{
    public function testValidGoalListIsReturnedUnchanged(): void
    {
        $body = '[{"id":1,"title":"Gran fondo","goal_type":"event","target_date":"2026-10-01","route_original_filename":"route.gpx","route_distance_meters":12345.6,"route_bounds":{"min_latitude":40.1,"max_latitude":40.2}}]';
        $seen = [];
        $client = new MockHttpClient(function (string $method, string $url, array $options) use (&$seen, $body): MockResponse {
            $seen = [$method, $url, $options];
            return new MockResponse($body, ['http_code' => 200]);
        });

        $response = $this->controller($client)->list($this->request('/api/goals', 'session=valid', 'goals-request'));

        self::assertSame(200, $response->getStatusCode());
        self::assertSame($body, $response->getContent());
        self::assertSame('GET', $seen[0]);
        self::assertSame('http://python.test/api/goals', $seen[1]);
        self::assertSame('goals-request', $response->headers->get('X-Request-Id'));
        self::assertCacheControl($response->headers->get('Cache-Control'));
    }

    public function testValidGoalDetailPreservesGoalReadAndGpxMetadata(): void
    {
        $body = '{"id":42,"title":"Mountain route","goal_type":"event","target_date":"2026-11-12","route_original_filename":"mountain.gpx","route_size_bytes":9876,"route_distance_meters":54321.1,"route_elevation_gain_meters":1234.5,"route_start_latitude":40.123,"route_start_longitude":-3.456,"route_end_latitude":40.789,"route_end_longitude":-3.987,"route_bounds":{"min_latitude":40.1,"min_longitude":-4.0,"max_latitude":40.8,"max_longitude":-3.4}}';
        $seen = [];
        $client = new MockHttpClient(function (string $method, string $url, array $options) use (&$seen, $body): MockResponse {
            $seen = [$method, $url, $options];
            return new MockResponse($body, ['http_code' => 200]);
        });

        $response = $this->controller($client)->detail($this->request('/api/goals/42', 'session=valid'), '42');

        self::assertSame(200, $response->getStatusCode());
        self::assertSame($body, $response->getContent());
        self::assertSame('http://python.test/api/goals/42', $seen[1]);
        self::assertCacheControl($response->headers->get('Cache-Control'));
    }

    public function testOnlyConfiguredSessionCookieAndSafeHeadersAreForwarded(): void
    {
        $seen = [];
        $client = new MockHttpClient(function (string $method, string $url, array $options) use (&$seen): MockResponse {
            $seen = [$method, $url, $options];
            return new MockResponse('[{"id":1}]', [
                'http_code' => 200,
                'response_headers' => ['set-cookie' => [
                    'session=refreshed; Path=/; Secure; HttpOnly; SameSite=Strict',
                    'tracking=discard; Path=/',
                ]],
            ]);
        });
        $request = $this->request('/api/goals?user_id=attacker&status=active', 'session=valid; tracking=secret', 'goal-request');
        $request->headers->set('Authorization', 'Bearer attacker');
        $request->headers->set('X-User-Id', '999');
        $request->headers->set('X-Forwarded-User', '999');
        $request->headers->set('X-JWT', 'attacker-token');
        $request->request->set('user_id', 'body-attacker');

        $response = $this->controller($client)->list($request);

        self::assertSame(200, $response->getStatusCode());
        self::assertContains('Cookie: session=valid', $seen[2]['headers']);
        self::assertFalse($this->hasHeader($seen[2]['headers'], 'tracking:'));
        self::assertFalse($this->hasHeader($seen[2]['headers'], 'authorization:'));
        self::assertFalse($this->hasHeader($seen[2]['headers'], 'x-user-id:'));
        self::assertFalse($this->hasHeader($seen[2]['headers'], 'x-forwarded-user:'));
        self::assertFalse($this->hasHeader($seen[2]['headers'], 'x-jwt:'));
        self::assertStringNotContainsString('user_id', $seen[1]);
        self::assertStringNotContainsString('status=', $seen[1]);
        $setCookies = $response->headers->all()['set-cookie'] ?? [];
        self::assertCount(1, $setCookies);
        self::assertStringContainsString('session=refreshed', $setCookies[0]);
        self::assertStringContainsString('samesite=strict', strtolower($setCookies[0]));
        self::assertStringNotContainsString('tracking=', $setCookies[0]);
    }

    public function testDifferentSessionsDoNotShareGoalListsOrDetails(): void
    {
        $client = new MockHttpClient(function (string $method, string $url, array $options): MockResponse {
            $cookie = $this->headerValue($options['headers'], 'cookie:');
            $id = str_contains($cookie, 'session=first') ? 1 : 2;
            if (str_ends_with($url, '/42')) {
                return new MockResponse(json_encode(['id' => $id, 'title' => 'Goal '.$id], JSON_THROW_ON_ERROR), ['http_code' => 200]);
            }

            return new MockResponse(json_encode([['id' => $id, 'title' => 'Goal '.$id]], JSON_THROW_ON_ERROR), ['http_code' => 200]);
        });
        $controller = $this->controller($client);

        $firstList = $controller->list($this->request('/api/goals', 'session=first'));
        $secondList = $controller->list($this->request('/api/goals', 'session=second'));
        $firstDetail = $controller->detail($this->request('/api/goals/42', 'session=first'), '42');
        $secondDetail = $controller->detail($this->request('/api/goals/42', 'session=second'), '42');

        self::assertStringContainsString('"id":1', (string) $firstList->getContent());
        self::assertStringContainsString('"id":2', (string) $secondList->getContent());
        self::assertStringContainsString('"id":1', (string) $firstDetail->getContent());
        self::assertStringContainsString('"id":2', (string) $secondDetail->getContent());
    }

    public function testPythonAuthorizationErrorsArePreserved(): void
    {
        foreach ([401, 403, 404, 422] as $status) {
            $body = json_encode(['detail' => 'Python semantic error'], JSON_THROW_ON_ERROR);
            $response = $this->controller(new MockHttpClient(new MockResponse($body, ['http_code' => $status])))
                ->detail($this->request('/api/goals/42', ''), '42');

            self::assertSame($status, $response->getStatusCode());
            self::assertSame($body, $response->getContent());
            self::assertCacheControl($response->headers->get('Cache-Control'));
        }
    }

    public function testDangerousGoalIdentifiersCannotAlterUpstreamPath(): void
    {
        $calls = 0;
        $client = new MockHttpClient(function () use (&$calls): MockResponse {
            ++$calls;
            return new MockResponse('{}', ['http_code' => 200]);
        });
        $controller = $this->controller($client);

        foreach (['../private', '42/../../users', '42?user_id=attacker', '42#fragment', ''] as $goalId) {
            $response = $controller->detail($this->request('/api/goals/'.rawurlencode($goalId), 'session=valid'), $goalId);
            self::assertSame(422, $response->getStatusCode(), $goalId);
            self::assertSame('INVALID_GOAL_ID', json_decode((string) $response->getContent(), true)['code']);
        }

        self::assertSame(0, $calls);
    }

    public function testUpstreamFailuresAndUnexpectedShapesAreSafeAndNotRetried(): void
    {
        $cases = [
            new MockResponse([new TransportException('timeout')]),
            new MockResponse('{"detail":"internal"}', ['http_code' => 500]),
            new MockResponse('not-json', ['http_code' => 200]),
            new MockResponse('{"id":1}', ['http_code' => 200]),
        ];

        foreach ($cases as $upstreamResponse) {
            $calls = 0;
            $client = new MockHttpClient(function () use (&$calls, $upstreamResponse): MockResponse {
                ++$calls;
                return $upstreamResponse;
            });

            $response = $this->controller($client)->list($this->request('/api/goals', 'session=valid'));
            $payload = json_decode((string) $response->getContent(), true, flags: JSON_THROW_ON_ERROR);

            self::assertContains($response->getStatusCode(), [502, 503]);
            self::assertContains($payload['code'], ['PYTHON_UPSTREAM_BAD_GATEWAY', 'PYTHON_UPSTREAM_UNAVAILABLE']);
            self::assertSame(1, $calls);
            self::assertCacheControl($response->headers->get('Cache-Control'));
            self::assertArrayNotHasKey('url', $payload);
            self::assertArrayNotHasKey('details', $payload);
        }
    }

    public function testRequestIdIsPreservedOrGenerated(): void
    {
        $client = new MockHttpClient(new MockResponse('[]', ['http_code' => 200]));
        $controller = $this->controller($client);

        $preserved = $controller->list($this->request('/api/goals', 'session=one', 'goals-123'));
        $generated = $controller->list($this->request('/api/goals', 'session=two'));

        self::assertSame('goals-123', $preserved->headers->get('X-Request-Id'));
        self::assertMatchesRegularExpression('/^gw-[a-f0-9]{32}$/', (string) $generated->headers->get('X-Request-Id'));
    }

    private function controller(MockHttpClient $client): GoalController
    {
        return new GoalController(
            new PythonSessionClient($client, 'http://python.test', 'session', 0.1, 0.2),
            new NullLogger(),
        );
    }

    private function request(string $uri, string $cookie, ?string $requestId = null): Request
    {
        $server = ['HTTP_COOKIE' => $cookie];
        if ($requestId !== null) {
            $server['HTTP_X_REQUEST_ID'] = $requestId;
        }

        return Request::create($uri, 'GET', [], $this->parseCookies($cookie), [], $server);
    }

    /** @return array<string, string> */
    private function parseCookies(string $header): array
    {
        $cookies = [];
        foreach (explode(';', $header) as $part) {
            [$name, $value] = array_pad(explode('=', trim($part), 2), 2, null);
            if ($name !== null && $value !== null && $name !== '') {
                $cookies[$name] = $value;
            }
        }

        return $cookies;
    }

    /** @param list<string> $headers */
    private function hasHeader(array $headers, string $prefix): bool
    {
        foreach ($headers as $header) {
            if (str_starts_with(strtolower($header), $prefix)) {
                return true;
            }
        }

        return false;
    }

    /** @param list<string> $headers */
    private function headerValue(array $headers, string $prefix): string
    {
        foreach ($headers as $header) {
            if (str_starts_with(strtolower($header), $prefix)) {
                return trim(substr($header, strlen($prefix)));
            }
        }

        return '';
    }

    private static function assertCacheControl(?string $value): void
    {
        self::assertNotNull($value);
        self::assertStringContainsString('private', $value);
        self::assertStringContainsString('no-store', $value);
    }
}
