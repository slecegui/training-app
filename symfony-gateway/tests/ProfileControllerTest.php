<?php

namespace App\Tests;

use App\Controller\ProfileController;
use App\Service\PythonSessionClient;
use PHPUnit\Framework\TestCase;
use Psr\Log\NullLogger;
use Symfony\Component\HttpClient\Exception\TransportException;
use Symfony\Component\HttpClient\MockHttpClient;
use Symfony\Component\HttpClient\Response\MockResponse;
use Symfony\Component\HttpFoundation\Request;

final class ProfileControllerTest extends TestCase
{
    public function testValidProfileIsReturnedUnchangedAndOnlySessionCookieIsForwarded(): void
    {
        $seen = [];
        $profile = '{"id":7,"sports":["road_cycling"],"experience_level":"intermediate","availability":{"mon":60},"power_zones":null,"heart_rate_zones":null,"preferences":{"units":"metric"},"injuries_or_constraints":null}';
        $client = new MockHttpClient(function (string $method, string $url, array $options) use (&$seen, $profile): MockResponse {
            $seen = [$method, $url, $options];
            return new MockResponse($profile, [
                'http_code' => 200,
                'response_headers' => ['set-cookie' => [
                    'session=refreshed; Path=/; Secure; HttpOnly; SameSite=Lax',
                    'tracking=discard-me; Path=/',
                ]],
            ]);
        });

        $request = $this->request('/api/profile?user_id=attacker', 'session=valid; tracking=secret', 'req-profile');
        $request->headers->set('Authorization', 'Bearer attacker');
        $request->headers->set('X-User-Id', '999');
        $request->headers->set('X-Forwarded-User', '999');
        $request->request->set('user_id', 'body-attacker');

        $response = $this->controller($client)->profile($request);

        self::assertSame(200, $response->getStatusCode());
        self::assertSame($profile, $response->getContent());
        self::assertCacheControl($response->headers->get('Cache-Control'));
        self::assertSame('req-profile', $response->headers->get('X-Request-Id'));
        self::assertSame('GET', $seen[0]);
        self::assertSame('http://python.test/api/profile', $seen[1]);
        self::assertContains('Cookie: session=valid', $seen[2]['headers']);
        self::assertFalse($this->hasHeader($seen[2]['headers'], 'tracking:'));
        self::assertFalse($this->hasHeader($seen[2]['headers'], 'authorization:'));
        self::assertFalse($this->hasHeader($seen[2]['headers'], 'x-user-id:'));
        self::assertFalse($this->hasHeader($seen[2]['headers'], 'x-forwarded-user:'));
        self::assertStringNotContainsString('user_id', $seen[1]);
        $setCookies = $response->headers->all()['set-cookie'] ?? [];
        self::assertCount(1, $setCookies);
        self::assertStringContainsString('session=refreshed', $setCookies[0]);
        self::assertStringContainsString('httponly', strtolower($setCookies[0]));
        self::assertStringContainsString('secure', strtolower($setCookies[0]));
        self::assertStringContainsString('samesite=lax', strtolower($setCookies[0]));
    }

    public function testSemanticErrorsFromPythonArePreserved(): void
    {
        foreach ([401, 403, 404, 422] as $status) {
            $body = json_encode(['detail' => 'Python response'], JSON_THROW_ON_ERROR);
            $response = $this->controller(new MockHttpClient(new MockResponse($body, ['http_code' => $status])))
                ->profile($this->request('/api/profile', ''));

            self::assertSame($status, $response->getStatusCode());
            self::assertSame($body, $response->getContent());
            self::assertCacheControl($response->headers->get('Cache-Control'));
        }
    }

    public function testDifferentSessionsReceiveDifferentProfilesWithoutReuse(): void
    {
        $calls = 0;
        $client = new MockHttpClient(function (string $method, string $url, array $options) use (&$calls): MockResponse {
            ++$calls;
            $cookie = $this->headerValue($options['headers'], 'cookie:');
            $id = str_contains($cookie, 'session=first') ? 1 : 2;
            return new MockResponse(json_encode(['id' => $id, 'sports' => []], JSON_THROW_ON_ERROR), ['http_code' => 200]);
        });
        $controller = $this->controller($client);

        $first = $controller->profile($this->request('/api/profile', 'session=first'));
        $second = $controller->profile($this->request('/api/profile', 'session=second'));

        self::assertSame('{"id":1,"sports":[]}', $first->getContent());
        self::assertSame('{"id":2,"sports":[]}', $second->getContent());
        self::assertSame(2, $calls);
    }

    public function testRequestIdIsPreservedOrGenerated(): void
    {
        $client = new MockHttpClient(new MockResponse('{"id":1}', ['http_code' => 200]));
        $controller = $this->controller($client);

        $preserved = $controller->profile($this->request('/api/profile', 'session=one', 'request-123'));
        $generated = $controller->profile($this->request('/api/profile', 'session=two'));

        self::assertSame('request-123', $preserved->headers->get('X-Request-Id'));
        self::assertMatchesRegularExpression('/^gw-[a-f0-9]{32}$/', (string) $generated->headers->get('X-Request-Id'));
    }

    public function testUnavailableUpstreamErrorsAreSafeAndNotRetried(): void
    {
        $cases = [
            new MockResponse([new TransportException('timeout')]),
            new MockResponse('{"detail":"internal"}', ['http_code' => 500]),
            new MockResponse('not-json', ['http_code' => 200]),
        ];

        foreach ($cases as $upstreamResponse) {
            $calls = 0;
            $client = new MockHttpClient(function () use (&$calls, $upstreamResponse): MockResponse {
                ++$calls;
                return $upstreamResponse;
            });

            $response = $this->controller($client)->profile($this->request('/api/profile', 'session=one'));
            $payload = json_decode((string) $response->getContent(), true, flags: JSON_THROW_ON_ERROR);

            self::assertContains($response->getStatusCode(), [502, 503]);
            self::assertContains($payload['code'], ['PYTHON_UPSTREAM_BAD_GATEWAY', 'PYTHON_UPSTREAM_UNAVAILABLE']);
            self::assertSame(1, $calls);
            self::assertCacheControl($response->headers->get('Cache-Control'));
            self::assertArrayNotHasKey('details', $payload);
            self::assertArrayNotHasKey('url', $payload);
        }
    }

    private function controller(MockHttpClient $client): ProfileController
    {
        return new ProfileController(
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
        self::assertStringContainsString('no-store', $value);
        self::assertStringContainsString('private', $value);
    }
}
