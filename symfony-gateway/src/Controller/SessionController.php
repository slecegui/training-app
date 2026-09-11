<?php

namespace App\Controller;

use App\Service\PythonSessionClient;
use Psr\Log\LoggerInterface;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\Routing\Attribute\Route;
use Symfony\Contracts\HttpClient\ResponseInterface;

final class SessionController
{
    private const REQUEST_ID_HEADER = 'X-Request-Id';
    private const REQUEST_ID_PATTERN = '/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/';
    private const PASSTHROUGH_STATUSES = [200, 401, 403, 404, 422];

    public function __construct(
        private readonly PythonSessionClient $pythonSessionClient,
        private readonly LoggerInterface $logger,
        private readonly string $sessionCookieName,
    ) {
    }

    #[Route('/api/auth/session', name: 'auth_session_proxy', methods: ['GET'])]
    public function session(Request $request): Response
    {
        $requestId = $this->requestId($request);

        try {
            $upstream = $this->pythonSessionClient->request($request, $requestId);
            $status = $upstream->getStatusCode();
            $body = $upstream->getContent(false);

            if (!in_array($status, self::PASSTHROUGH_STATUSES, true) || !$this->isJson($body)) {
                $this->logUpstreamFailure($requestId, $status, 'invalid_status_or_json');

                return $this->safeError(Response::HTTP_BAD_GATEWAY, 'PYTHON_UPSTREAM_BAD_GATEWAY', $requestId);
            }

            $headers = [
                'Content-Type' => 'application/json',
                self::REQUEST_ID_HEADER => $requestId,
            ];
            $setCookies = $this->pythonSessionClient->allowedSessionCookies($upstream);
            if ($setCookies !== []) {
                $headers['Set-Cookie'] = $setCookies;
            }

            return new Response($body, $status, $headers);
        } catch (\Throwable $exception) {
            $this->logger->error('Python session proxy failed', [
                'event' => 'python_session_proxy_failed',
                'request_id' => $requestId,
                'exception_class' => $exception::class,
            ]);

            return $this->safeError(Response::HTTP_SERVICE_UNAVAILABLE, 'PYTHON_UPSTREAM_UNAVAILABLE', $requestId);
        }
    }

    private function requestId(Request $request): string
    {
        $incoming = $request->headers->get(self::REQUEST_ID_HEADER);
        if ($incoming !== null && preg_match(self::REQUEST_ID_PATTERN, $incoming) === 1) {
            return $incoming;
        }

        return 'gw-'.bin2hex(random_bytes(16));
    }

    private function isJson(string $body): bool
    {
        if ($body === '') {
            return false;
        }

        $decoded = json_decode($body, true);

        return is_array($decoded) && json_last_error() === JSON_ERROR_NONE;
    }

    private function safeError(int $status, string $code, string $requestId): JsonResponse
    {
        return new JsonResponse([
            'status' => 'error',
            'code' => $code,
            'request_id' => $requestId,
        ], $status, [self::REQUEST_ID_HEADER => $requestId]);
    }

    private function logUpstreamFailure(string $requestId, int $status, string $reason): void
    {
        $this->logger->error('Python session proxy received an unusable response', [
            'event' => 'python_session_proxy_invalid_response',
            'request_id' => $requestId,
            'upstream_status' => $status,
            'reason' => $reason,
        ]);
    }
}
