<?php

namespace App\Tests;

use Symfony\Bundle\FrameworkBundle\Test\WebTestCase;
use Symfony\Component\HttpClient\MockHttpClient;
use Symfony\Component\HttpClient\Response\MockResponse;
use Symfony\Contracts\HttpClient\HttpClientInterface;

final class SessionHttpTest extends WebTestCase
{
    public function testSessionRouteReturnsPythonUserRead(): void
    {
        $client = static::createClient();
        $mock = new MockHttpClient(new MockResponse('{"id":3,"email":"user@example.test","name":"User"}', ['http_code' => 200]));
        static::getContainer()->set(HttpClientInterface::class, $mock);

        $client->request('GET', '/api/auth/session', server: [
            'HTTP_COOKIE' => 'session=python-session',
            'HTTP_X_REQUEST_ID' => 'http-session-request',
        ]);

        self::assertResponseStatusCodeSame(200);
        self::assertSame('http-session-request', $client->getResponse()->headers->get('X-Request-Id'));
        self::assertJsonStringEqualsJsonString(
            '{"id":3,"email":"user@example.test","name":"User"}',
            (string) $client->getResponse()->getContent(),
        );
    }

    public function testSessionRouteKeepsPython401(): void
    {
        $client = static::createClient();
        $mock = new MockHttpClient(new MockResponse('{"detail":"Sesión requerida"}', ['http_code' => 401]));
        static::getContainer()->set(HttpClientInterface::class, $mock);

        $client->request('GET', '/api/auth/session', server: ['HTTP_X_REQUEST_ID' => 'http-session-401']);

        self::assertResponseStatusCodeSame(401);
        self::assertJsonStringEqualsJsonString(
            '{"detail":"Sesión requerida"}',
            (string) $client->getResponse()->getContent(),
        );
    }
}
