<?php

namespace App\Service;

use Symfony\Component\HttpFoundation\Request;
use Symfony\Contracts\HttpClient\HttpClientInterface;
use Symfony\Contracts\HttpClient\ResponseInterface;

final class PythonSessionClient
{
    public function __construct(
        private readonly HttpClientInterface $httpClient,
        private readonly string $baseUrl,
        private readonly string $sessionCookieName,
        private readonly float $connectTimeout,
        private readonly float $readTimeout,
    ) {
        if (preg_match("/^[!#-'*+\\-.^_`|~0-9A-Za-z]+$/", $sessionCookieName) !== 1) {
            throw new \InvalidArgumentException('The configured session cookie name is invalid.');
        }
    }

    public function request(Request $request, string $requestId): ResponseInterface
    {
        return $this->requestReadOnly($request, $requestId, '/api/auth/session');
    }

    public function requestProfile(Request $request, string $requestId): ResponseInterface
    {
        return $this->requestReadOnly($request, $requestId, '/api/profile');
    }

    /** @return list<string> */
    public function allowedSessionCookies(ResponseInterface $upstream): array
    {
        $allowed = [];
        foreach ($upstream->getHeaders(false)['set-cookie'] ?? [] as $rawCookie) {
            try {
                $cookie = \Symfony\Component\HttpFoundation\Cookie::fromString($rawCookie);
            } catch (\Throwable) {
                continue;
            }

            if ($cookie->getName() === $this->sessionCookieName) {
                $allowed[] = (string) $cookie;
            }
        }

        return $allowed;
    }

    private function requestReadOnly(Request $request, string $requestId, string $path): ResponseInterface
    {
        $headers = [
            'Accept' => 'application/json',
            'X-Request-Id' => $requestId,
        ];

        $cookieValue = $request->cookies->get($this->sessionCookieName);
        if (is_string($cookieValue) && $this->isSafeCookieValue($cookieValue)) {
            $headers['Cookie'] = $this->sessionCookieName.'='.$cookieValue;
        }

        return $this->httpClient->request('GET', rtrim($this->baseUrl, '/').$path, [
            'headers' => $headers,
            'timeout' => $this->readTimeout,
            'max_redirects' => 0,
            'extra' => [
                'curl' => [
                    CURLOPT_CONNECTTIMEOUT_MS => max(1, (int) round($this->connectTimeout * 1000)),
                ],
            ],
        ]);
    }

    private function isSafeCookieValue(string $value): bool
    {
        return $value !== '' && preg_match('/^[^\\x00-\\x20\\x7f;,\\"]+$/D', $value) === 1;
    }
}
