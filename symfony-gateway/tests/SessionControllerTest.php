<?php

namespace App\Tests;

use App\Controller\SessionController;
use App\Service\PythonSessionClient;
use PHPUnit\Framework\TestCase;
use Psr\Log\NullLogger;
use Symfony\Component\HttpClient\Exception\TransportException;
use Symfony\Component\HttpClient\MockHttpClient;
use Symfony\Component\HttpClient\Response\MockResponse;
use Symfony\Component\HttpFoundation\Request;

final class SessionControllerTest extends TestCase
{
    public function testValidSessionForwardsOnlyConfiguredCookieAndReturnsUserRead(): void
    {
        $seen = [];
        $client = new MockHttpClient(function (string $method, string $url, array $options) use (&$seen): MockResponse {
            $seen = [$method, $url, $options];

            return new MockResponse('{"id":7,"email":"rider@example.test","name":"Rider"}', [
                'http_code' => 200,
                'response_headers' => [
                    'set-cookie' => [
                        'session=refreshed; Path=/; Secure; HttpOnly; SameSite=Lax',
                        'tracking=discard-me; Path=/',
                    ],
                ],
            ]);
        });
        $request = $this->request(
            '/api/auth/session?user_id=attacker',
            'session=valid-cookie; tracking=discard-me',
            'client-request-7',
            'Bearer must-not-forward',
            '999',
        );
        $request->request->set('user_id', 'body-attacker');

        $response = $this->controller($client)->session($request);

        self::assertSame(200, $response->getStatusCode());
        self::assertSame('{"id":7,"email":"rider@example.test","name":"Rider"}', $response->getContent());
        self::assertSame('client-request-7', $response->headers->get('X-Request-Id'));
        self::assertSame('GET', $seen[0]);
        self::assertSame('http://python.test/api/auth/session', $seen[1]);
        self::assertContains('Cookie: session=valid-cookie', $seen[2]['headers']);
        self::assertFalse($this->hasHeader($seen[2]['headers'], 'tracking:'));
        self::assertFalse($this->hasHeader($seen[2]['headers'], 'authorization:'));
        self::assertFalse($this->hasHeader($seen[2]['headers'], 'x-user-id:'));
        self::assertFalse($this->hasHeader($seen[2]['headers'], 'x-forwarded-user:'));
        self::assertStringNotContainsString('user_id', $seen[1]);
    }

    public function testSessionSetCookieIsPreservedAndForeignCookiesAreDropped(): void
    {
        $client = new MockHttpClient(new MockResponse('{"id":7}', [
            'http_code' => 200,
            'response_headers' => [
                'set-cookie' => [
                    'session=refreshed; Path=/account; Secure; HttpOnly; SameSite=Strict',
                    'other=secret; Path=/; Secure',
                ],
            ],
        ]));

        $response = $this->controller($client)->session($this->request('/api/auth/session', 'session=old'));
        $setCookies = $response->headers->all()['set-cookie'] ?? [];

        self::assertCount(1, $setCookies);
        self::assertStringContainsString('session=refreshed', $setCookies[0]);
        self::assertStringContainsString('path=/account', strtolower($setCookies[0]));
        self::assertStringContainsString('secure', strtolower($setCookies[0]));
        self::assertStringContainsString('httponly', strtolower($setCookies[0]));
        self::assertStringContainsString('samesite=strict', strtolower($setCookies[0]));
        self::assertStringNotContainsString('other=', $setCookies[0]);
    }

    public function testAbsentSessionPreservesPython401AndDoesNotSendCookie(): void
    {
        $seen = [];
        $client = new MockHttpClient(function (string $method, string $url, array $options) use (&$seen): MockResponse {
            $seen = $options;
            return new MockResponse('{"detail":"Sesión requerida"}', ['http_code' => 401]);
        });

        $response = $this->controller($client)->session($this->request('/api/auth/session', 'tracking=not-allowed'));

        self::assertSame(401, $response->getStatusCode());
        self::assertSame('{"detail":"Sesión requerida"}', $response->getContent());
        self::assertFalse($this->hasHeader($seen['headers'], 'cookie:'));
    }

    public function testInvalidSessionPreservesPythonRejection(): void
    {
        $client = new MockHttpClient(new MockResponse('{"detail":"Sesión no válida"}', ['http_code' => 401]));

        $response = $this->controller($client)->session($this->request('/api/auth/session', 'session=tampered'));

        self::assertSame(401, $response->getStatusCode());
        self::assertSame('{"detail":"Sesión no válida"}', $response->getContent());
    }

    public function testDifferentSessionsAreNotCachedOrReused(): void
    {
        $cookies = [];
        $client = new MockHttpClient(function (string $method, string $url, array $options) use (&$cookies): MockResponse {
            $cookie = array_values(array_filter(
                $options['headers'],
                static fn (string $header): bool => str_starts_with($header, 'Cookie:'),
            ))[0] ?? '';
            $cookies[] = $cookie;
            $id = str_contains($cookie, 'session=first') ? 1 : 2;
            return new MockResponse(json_encode(['id' => $id, 'email' => $id.'@example.test', 'name' => 'Rider']), ['http_code' => 200]);
        });
        $controller = $this->controller($client);

        $first = $controller->session($this->request('/api/auth/session', 'session=first'));
        $second = $controller->session($this->request('/api/auth/session', 'session=second'));

        self::assertSame('{"id":1,"email":"1@example.test","name":"Rider"}', $first->getContent());
        self::assertSame('{"id":2,"email":"2@example.test","name":"Rider"}', $second->getContent());
        self::assertSame(['Cookie: session=first', 'Cookie: session=second'], $cookies);
    }

    public function testRequestIdIsPreservedOrGenerated(): void
    {
        $client = new MockHttpClient(new MockResponse('{"id":1}', ['http_code' => 200]));
        $controller = $this->controller($client);

        $preserved = $controller->session($this->request('/api/auth/session', 'session=one', 'request-123'));
        $generated = $controller->session($this->request('/api/auth/session', 'session=two'));

        self::assertSame('request-123', $preserved->headers->get('X-Request-Id'));
        self::assertMatchesRegularExpression('/^gw-[a-f0-9]{32}$/', (string) $generated->headers->get('X-Request-Id'));
    }

    public function testTimeoutConnectionFailureFiveHundredAndInvalidJsonAreSafeAndNotRetried(): void
    {
        $cases = [
            'timeout' => new MockResponse([new TransportException('timeout')]),
            'server-error' => new MockResponse('{"detail":"internal"}', ['http_code' => 500]),
            'invalid-json' => new MockResponse('not-json', ['http_code' => 200]),
        ];

        foreach ($cases as $name => $mockResponse) {
            $calls = 0;
            $client = new MockHttpClient(function () use (&$calls, $mockResponse): MockResponse {
                ++$calls;
                return $mockResponse;
            });

            $response = $this->controller($client)->session($this->request('/api/auth/session', 'session=one'));
            $payload = json_decode((string) $response->getContent(), true, flags: JSON_THROW_ON_ERROR);

            self::assertContains($response->getStatusCode(), [502, 503], $name);
            self::assertContains($payload['code'], ['PYTHON_UPSTREAM_BAD_GATEWAY', 'PYTHON_UPSTREAM_UNAVAILABLE'], $name);
            self::assertSame(1, $calls, $name);
            self::assertArrayNotHasKey('details', $payload, $name);
        }
    }

    private function controller(MockHttpClient $client): SessionController
    {
        return new SessionController(
            new PythonSessionClient($client, 'http://python.test', 'session', 0.1, 0.2),
            new NullLogger(),
            'session',
        );
    }

    private function request(string $uri, string $cookie, ?string $requestId = null, ?string $authorization = null, ?string $userId = null): Request
    {
        $server = ['HTTP_COOKIE' => $cookie];
        if ($requestId !== null) {
            $server['HTTP_X_REQUEST_ID'] = $requestId;
        }
        if ($authorization !== null) {
            $server['HTTP_AUTHORIZATION'] = $authorization;
        }
        if ($userId !== null) {
            $server['HTTP_X_USER_ID'] = $userId;
            $server['HTTP_X_FORWARDED_USER'] = $userId;
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
}
