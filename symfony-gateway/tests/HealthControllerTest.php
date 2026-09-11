<?php

namespace App\Tests;

use App\Controller\HealthController;
use App\Service\PythonHealthClient;
use PHPUnit\Framework\TestCase;
use Psr\Log\NullLogger;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpClient\MockHttpClient;
use Symfony\Component\HttpClient\Exception\TransportException;
use Symfony\Component\HttpClient\Response\MockResponse;

final class HealthControllerTest extends TestCase
{
    public function testLivenessDoesNotCallHttp(): void
    {
        $calls = 0;
        $client = new MockHttpClient(function () use (&$calls): MockResponse {
            ++$calls;
            return new MockResponse('{}');
        });
        $controller = $this->controller($client);

        $response = $controller->liveness();

        self::assertSame(200, $response->getStatusCode());
        self::assertSame(
            ['status' => 'ok', 'service' => 'symfony-gateway'],
            json_decode((string) $response->getContent(), true, flags: JSON_THROW_ON_ERROR),
        );
        self::assertSame(0, $calls);
    }

    public function testReadinessPreservesRequestIdAndCallsOnlyHealthEndpoint(): void
    {
        $seen = [];
        $client = new MockHttpClient(function (string $method, string $url, array $options) use (&$seen): MockResponse {
            $seen = [$method, $url, $options];
            return new MockResponse('{"status":"ok"}', ['http_code' => 200]);
        });
        $controller = $this->controller($client);
        $request = Request::create('/health/ready?user_id=should-not-propagate');
        $request->request->set('user_id', 'should-not-propagate');
        $request->headers->set('X-Request-Id', 'client-request-123');
        $request->headers->set('X-User-Id', 'should-not-propagate');

        $response = $controller->readiness($request);

        self::assertSame(200, $response->getStatusCode());
        self::assertSame('client-request-123', $response->headers->get('X-Request-Id'));
        self::assertSame('GET', $seen[0]);
        self::assertSame('http://python.test/api/health', $seen[1]);
        self::assertContains('X-Request-Id: client-request-123', $seen[2]['headers']);
        self::assertFalse((bool) array_filter(
            $seen[2]['headers'],
            static fn (string $header): bool => str_starts_with(strtolower($header), 'x-user-id:'),
        ));
        self::assertStringNotContainsString('user_id', $seen[1]);
    }

    public function testReadinessGeneratesRequestIdWhenMissing(): void
    {
        $client = new MockHttpClient(new MockResponse('{"status":"ok"}', ['http_code' => 200]));
        $response = $this->controller($client)->readiness(Request::create('/health/ready'));

        self::assertSame(200, $response->getStatusCode());
        self::assertMatchesRegularExpression('/^gw-[a-f0-9]{32}$/', (string) $response->headers->get('X-Request-Id'));
    }

    public function testInvalidRequestIdIsReplacedAndNotForwarded(): void
    {
        $forwarded = null;
        $client = new MockHttpClient(function (string $method, string $url, array $options) use (&$forwarded): MockResponse {
            $forwarded = array_values(array_filter(
                $options['headers'],
                static fn (string $header): bool => str_starts_with($header, 'X-Request-Id:'),
            ))[0] ?? null;
            return new MockResponse('{"status":"ok"}', ['http_code' => 200]);
        });

        $request = Request::create('/health/ready');
        $request->headers->set('X-Request-Id', 'bad value with whitespace');
        $response = $this->controller($client)->readiness($request);

        self::assertMatchesRegularExpression('/^gw-[a-f0-9]{32}$/', (string) $response->headers->get('X-Request-Id'));
        self::assertSame('X-Request-Id: '.$response->headers->get('X-Request-Id'), $forwarded);
    }

    public function testTimeoutIsConvertedTo503WithoutRetry(): void
    {
        $calls = 0;
        $client = new MockHttpClient(function () use (&$calls): MockResponse {
            ++$calls;
            return new MockResponse([new TransportException('simulated timeout')]);
        });

        $response = $this->controller($client)->readiness(Request::create('/health/ready'));

        self::assertSame(503, $response->getStatusCode());
        self::assertSame(1, $calls);
        self::assertSame('PYTHON_UPSTREAM_UNAVAILABLE', json_decode((string) $response->getContent(), true)['code']);
    }

    public function testInvalidUpstreamBodyIsConvertedTo503WithoutRetry(): void
    {
        $calls = 0;
        $client = new MockHttpClient(function () use (&$calls): MockResponse {
            ++$calls;
            return new MockResponse('{"unexpected":"payload"}', ['http_code' => 200]);
        });

        $response = $this->controller($client)->readiness(Request::create('/health/ready'));

        self::assertSame(503, $response->getStatusCode());
        self::assertSame(1, $calls);
    }

    private function controller(MockHttpClient $client): HealthController
    {
        return new HealthController(
            new PythonHealthClient($client, 'http://python.test', 0.1, 0.2),
            new NullLogger(),
        );
    }
}
