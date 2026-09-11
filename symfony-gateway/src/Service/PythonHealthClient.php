<?php

namespace App\Service;

use Symfony\Contracts\HttpClient\HttpClientInterface;

final class PythonHealthClient
{
    public function __construct(
        private readonly HttpClientInterface $httpClient,
        private readonly string $baseUrl,
        private readonly float $connectTimeout,
        private readonly float $readTimeout,
    ) {
    }

    public function assertHealthy(string $requestId): void
    {
        $response = $this->httpClient->request('GET', rtrim($this->baseUrl, '/').'/api/health', [
            'headers' => [
                'Accept' => 'application/json',
                'X-Request-Id' => $requestId,
            ],
            'timeout' => $this->readTimeout,
            'max_redirects' => 0,
            'extra' => [
                'curl' => [
                    CURLOPT_CONNECTTIMEOUT_MS => max(1, (int) round($this->connectTimeout * 1000)),
                ],
            ],
        ]);

        if ($response->getStatusCode() !== 200) {
            throw new \RuntimeException('Unexpected Python health status.');
        }

        $payload = $response->toArray(false);
        if (($payload['status'] ?? null) !== 'ok') {
            throw new \RuntimeException('Invalid Python health payload.');
        }
    }
}
