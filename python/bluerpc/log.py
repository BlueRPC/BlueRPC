import logging
from typing import Any, Callable

import grpc
from grpc_interceptor.exceptions import GrpcException
from grpc_interceptor.server import AsyncServerInterceptor

_LOGGER = logging.getLogger(__name__)


class AsyncLoggingInterceptor(AsyncServerInterceptor):
    def __init__(self) -> None:
        super().__init__()
        _LOGGER.debug("Logger interceptor initialized")

    async def intercept(
        self,
        method: Callable,
        request_or_iterator: Any,
        context: grpc.ServicerContext,
        method_name: str,
    ) -> Any:
        _LOGGER.debug(f"[request] {method_name}: {request_or_iterator}")
        try:
            response_or_iterator = method(request_or_iterator, context)
            if not hasattr(response_or_iterator, "__aiter__"):
                # Unary, just await and return the response
                resp = await response_or_iterator
                _LOGGER.debug(f"[response] {method_name}: {resp}")
                return resp
        except GrpcException as e:
            await context.set_code(e.status_code)
            await context.set_details(e.details)
            raise

        # Server streaming responses, delegate to an async generator helper.
        # Note that we do NOT await this.
        return self._intercept_streaming(response_or_iterator, context)

    async def _intercept_streaming(self, iterator, context):
        try:
            async for r in iterator:
                yield r
        except GrpcException as e:
            await context.set_code(e.status_code)
            await context.set_details(e.details)
            raise
