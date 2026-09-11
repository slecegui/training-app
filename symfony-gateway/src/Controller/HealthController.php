<?php

namespace App\Controller;

use App\Service\PythonHealthClient;
use Psr\Log\LoggerInterface;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\Routing\Attribute\Route;

final class HealthController
{
    private const REQUEST_ID_HEADER = 'X-Request-Id';
    private const REQUEST_ID_PATTERN = '/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/';

    public function __construct(
        private readonly PythonHealthClient $pythonHealthClient,
        private readonly LoggerInterface $logger,
    ) {
    }

    #[Route('/health', name: 'health_liveness', methods: ['GET'])]
    public function liveness(): JsonResponse
    {
        return new JsonResponse([
            'status' => 'ok',
            'service' => 'symfony-gateway',
        ]);
    }

    #[Route('/health/ready', name: 'health_readiness', methods: ['GET'])]
    public function readiness(Request $request): JsonResponse
    {
        $requestId = $this->requestId($request);

        try {
            $this->pythonHealthClient->assertHealthy($requestId);

            return new JsonResponse([
                'status' => 'ok',
                'service' => 'symfony-gateway',
                'upstream' => 'ok',
            ], Response::HTTP_OK, [self::REQUEST_ID_HEADER => $requestId]);
        } catch (\Throwable $exception) {
            $this->logger->error('Python upstream readiness check failed', [
                'event' => 'python_upstream_readiness_failed',
                'request_id' => $requestId,
                'exception_class' => $exception::class,
            ]);

            return new JsonResponse([
                'status' => 'unavailable',
                'code' => 'PYTHON_UPSTREAM_UNAVAILABLE',
                'request_id' => $requestId,
            ], Response::HTTP_SERVICE_UNAVAILABLE, [self::REQUEST_ID_HEADER => $requestId]);
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
}
