<?php

namespace App\Tests;

use Symfony\Bundle\FrameworkBundle\Test\WebTestCase;
use Symfony\Component\HttpClient\MockHttpClient;
use Symfony\Component\HttpClient\Response\MockResponse;
use Symfony\Contracts\HttpClient\HttpClientInterface;

final class HealthHttpTest extends WebTestCase
{
    public function testHealthHttpEndpointIsLocalOnly(): void
    {
        $client = static::createClient();
        $mock = new MockHttpClient(new MockResponse('{"status":"ok"}', ['http_code' => 200]));
        static::getContainer()->set(HttpClientInterface::class, $mock);

        $client->request('GET', '/health');

        self::assertResponseIsSuccessful();
        self::assertJsonStringEqualsJsonString(
            '{"status":"ok","service":"symfony-gateway"}',
            (string) $client->getResponse()->getContent(),
        );
    }

    public function testReadinessHttpEndpointReturnsUpstreamStatus(): void
    {
        $client = static::createClient();
        $mock = new MockHttpClient(new MockResponse('{"status":"ok"}', ['http_code' => 200]));
        static::getContainer()->set(HttpClientInterface::class, $mock);

        $client->request('GET', '/health/ready', server: ['HTTP_X_REQUEST_ID' => 'http-test-request']);

        self::assertResponseIsSuccessful();
        self::assertSame('http-test-request', $client->getResponse()->headers->get('X-Request-Id'));
        self::assertJsonStringEqualsJsonString(
            '{"status":"ok","service":"symfony-gateway","upstream":"ok"}',
            (string) $client->getResponse()->getContent(),
        );
    }

    public function testReadinessReturns503ForUpstreamFailure(): void
    {
        $client = static::createClient();
        $mock = new MockHttpClient(new MockResponse('{"status":"down"}', ['http_code' => 503]));
        static::getContainer()->set(HttpClientInterface::class, $mock);

        $client->request('GET', '/health/ready', server: ['HTTP_X_REQUEST_ID' => 'upstream-failure']);

        self::assertResponseStatusCodeSame(503);
        self::assertJsonStringEqualsJsonString(
            '{"status":"unavailable","code":"PYTHON_UPSTREAM_UNAVAILABLE","request_id":"upstream-failure"}',
            (string) $client->getResponse()->getContent(),
        );
    }
}
