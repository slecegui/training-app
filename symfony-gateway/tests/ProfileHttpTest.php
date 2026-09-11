<?php

namespace App\Tests;

use Symfony\Bundle\FrameworkBundle\Test\WebTestCase;
use Symfony\Component\HttpClient\MockHttpClient;
use Symfony\Component\HttpClient\Response\MockResponse;
use Symfony\Contracts\HttpClient\HttpClientInterface;

final class ProfileHttpTest extends WebTestCase
{
    public function testProfileRouteReturnsPythonProfileWithoutCaching(): void
    {
        $client = static::createClient();
        $mock = new MockHttpClient(new MockResponse('{"id":3,"sports":[]}', ['http_code' => 200]));
        static::getContainer()->set(HttpClientInterface::class, $mock);

        $client->request('GET', '/api/profile', server: [
            'HTTP_COOKIE' => 'session=python-session',
            'HTTP_X_REQUEST_ID' => 'http-profile-request',
        ]);

        self::assertResponseStatusCodeSame(200);
        self::assertSame('http-profile-request', $client->getResponse()->headers->get('X-Request-Id'));
        self::assertStringContainsString('private', (string) $client->getResponse()->headers->get('Cache-Control'));
        self::assertStringContainsString('no-store', (string) $client->getResponse()->headers->get('Cache-Control'));
        self::assertJsonStringEqualsJsonString(
            '{"id":3,"sports":[]}',
            (string) $client->getResponse()->getContent(),
        );
    }

    public function testProfileRouteKeepsPython401(): void
    {
        $client = static::createClient();
        $mock = new MockHttpClient(new MockResponse('{"detail":"Sesión requerida"}', ['http_code' => 401]));
        static::getContainer()->set(HttpClientInterface::class, $mock);

        $client->request('GET', '/api/profile', server: ['HTTP_X_REQUEST_ID' => 'http-profile-401']);

        self::assertResponseStatusCodeSame(401);
        self::assertJsonStringEqualsJsonString(
            '{"detail":"Sesión requerida"}',
            (string) $client->getResponse()->getContent(),
        );
    }
}
