<?php

namespace App\Tests;

use Symfony\Bundle\FrameworkBundle\Test\WebTestCase;
use Symfony\Component\HttpClient\MockHttpClient;
use Symfony\Component\HttpClient\Response\MockResponse;
use Symfony\Contracts\HttpClient\HttpClientInterface;

final class GoalHttpTest extends WebTestCase
{
    public function testGoalsRoutesAreExposedThroughSymfony(): void
    {
        $client = static::createClient();
        $mock = new MockHttpClient(new MockResponse('[{"id":3,"title":"Goal"}]', ['http_code' => 200]));
        static::getContainer()->set(HttpClientInterface::class, $mock);

        $client->request('GET', '/api/goals', server: [
            'HTTP_COOKIE' => 'session=python-session',
            'HTTP_X_REQUEST_ID' => 'http-goals-request',
        ]);

        self::assertResponseStatusCodeSame(200);
        self::assertSame('http-goals-request', $client->getResponse()->headers->get('X-Request-Id'));
        self::assertJsonStringEqualsJsonString('[{"id":3,"title":"Goal"}]', (string) $client->getResponse()->getContent());

    }

    public function testGoalDetailRouteIsExposedThroughSymfony(): void
    {
        $client = static::createClient();
        $mock = new MockHttpClient(new MockResponse('{"id":3,"title":"Goal"}', ['http_code' => 200]));
        static::getContainer()->set(HttpClientInterface::class, $mock);

        $client->request('GET', '/api/goals/3', server: ['HTTP_COOKIE' => 'session=python-session']);

        self::assertResponseStatusCodeSame(200);
        self::assertJsonStringEqualsJsonString('{"id":3,"title":"Goal"}', (string) $client->getResponse()->getContent());
    }
}
