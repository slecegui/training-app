<?php

namespace App\Controller;

use App\Service\PythonSessionClient;
use Psr\Log\LoggerInterface;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\Routing\Attribute\Route;

final class GoalController
{
    private const REQUEST_ID_HEADER = 'X-Request-Id';
    private const REQUEST_ID_PATTERN = '/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/';
    private const PASSTHROUGH_STATUSES = [200, 401, 403, 404, 422];

    public function __construct(
        private readonly PythonSessionClient $pythonSessionClient,
        private readonly LoggerInterface $logger,
    ) {
    }

    #[Route('/api/goals', name: 'goals_proxy', methods: ['GET'])]
    public function list(Request $request): Response
    {
        $requestId = $this->requestId($request);

        try {
            $upstream = $this->pythonSessionClient->requestGoals($request, $requestId);

            return $this->forwardResponse($upstream, $requestId, true);
        } catch (\Throwable $exception) {
            return $this->unavailable($requestId, $exception);
        }
    }

    #[Route('/api/goals/{goalId}', name: 'goal_proxy', methods: ['GET'])]
    public function detail(Request $request, string $goalId): Response
    {
        $requestId = $this->requestId($request);

        try {
            $upstream = $this->pythonSessionClient->requestGoal($request, $requestId, $goalId);

            return $this->forwardResponse($upstream, $requestId, false);
        } catch (\InvalidArgumentException) {
            return $this->safeError(Response::HTTP_UNPROCESSABLE_ENTITY, 'INVALID_GOAL_ID', $requestId);
        } catch (\Throwable $exception) {
            return $this->unavailable($requestId, $exception);
        }
    }

    private function forwardResponse(\Symfony\Contracts\HttpClient\ResponseInterface $upstream, string $requestId, bool $expectsList): Response
    {
        $status = $upstream->getStatusCode();
        $body = $upstream->getContent(false);
        $validJson = $this->isJson($body);
        $validShape = $status !== Response::HTTP_OK || ($validJson && $this->hasExpectedShape($body, $expectsList));

        if (!in_array($status, self::PASSTHROUGH_STATUSES, true) || !$validJson || !$validShape) {
            $this->logger->error('Python goals proxy received an unusable response', [
                'event' => 'python_goals_proxy_invalid_response',
                'request_id' => $requestId,
                'upstream_status' => $status,
                'reason' => 'invalid_status_json_or_shape',
            ]);

            return $this->safeError(Response::HTTP_BAD_GATEWAY, 'PYTHON_UPSTREAM_BAD_GATEWAY', $requestId);
        }

        $headers = [
            'Content-Type' => 'application/json',
            'Cache-Control' => 'private, no-store',
            self::REQUEST_ID_HEADER => $requestId,
        ];
        $setCookies = $this->pythonSessionClient->allowedSessionCookies($upstream);
        if ($setCookies !== []) {
            $headers['Set-Cookie'] = $setCookies;
        }

        return new Response($body, $status, $headers);
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

        return json_last_error() === JSON_ERROR_NONE && is_array($decoded);
    }

    private function hasExpectedShape(string $body, bool $expectsList): bool
    {
        $decoded = json_decode($body, true);

        return $expectsList ? array_is_list($decoded) : !array_is_list($decoded);
    }

    private function unavailable(string $requestId, \Throwable $exception): JsonResponse
    {
        $this->logger->error('Python goals proxy failed', [
            'event' => 'python_goals_proxy_failed',
            'request_id' => $requestId,
            'exception_class' => $exception::class,
        ]);

        return $this->safeError(Response::HTTP_SERVICE_UNAVAILABLE, 'PYTHON_UPSTREAM_UNAVAILABLE', $requestId);
    }

    private function safeError(int $status, string $code, string $requestId): JsonResponse
    {
        return new JsonResponse([
            'status' => 'error',
            'code' => $code,
            'request_id' => $requestId,
        ], $status, [
            self::REQUEST_ID_HEADER => $requestId,
            'Cache-Control' => 'private, no-store',
        ]);
    }
}
