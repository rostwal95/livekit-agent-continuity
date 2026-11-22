"""Opt-in origin-bound v3 facades over the existing opaque P1 authority."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from continuity_lab.execution_api import AttemptResult, ExecutionObservation, ExecutionPort
from continuity_lab.work_api import TaskExecutionPort, WorkRecord

from ._policy_codec import CHANNEL_CODEC, _ChannelInvocation
from .channel_policy_contracts import ChannelPolicyRequest, ChannelPolicyResult
from .contracts import ContractError, Scope
from .coordinator import CaseAuthorityPort, CoordinatorError, _Call, _CoordinatorCore, _uuid
from .fixed_policy import _snapshot_fixed_policy_pair
from .fixed_policy_execution import FixedPolicyInvocationPort
from .runner import Applicability, DelegationRunError, _RunnerCore
from .security import EvidenceRecord


@dataclass(frozen=True, slots=True)
class ChannelPolicyView:
    record: WorkRecord
    request: ChannelPolicyRequest = field(repr=False)


@dataclass(frozen=True, slots=True)
class ChannelPolicySubmission:
    view: ChannelPolicyView
    created: bool


@dataclass(frozen=True, slots=True)
class ChannelPolicyExecutionView:
    execution: ExecutionObservation
    request: ChannelPolicyRequest = field(repr=False)
    result: ChannelPolicyResult | None = field(repr=False)
    applicability: Applicability


@dataclass(frozen=True, slots=True)
class ChannelPolicyRun:
    view: ChannelPolicyExecutionView
    invoked: bool
    recorded: AttemptResult | None = field(default=None, repr=False)


@runtime_checkable
class _BatchWorkReader(Protocol):
    async def get_many(self, *, work_ids: tuple[str, ...]) -> dict[str, WorkRecord]: ...


class ChannelPolicyCoordinator(_CoordinatorCore[ChannelPolicyRequest, ChannelPolicyResult]):
    """Exact submit and explicit first-origin accept share one bounded schedule.

    The original scoped operation UUID selects one P1 key. ``accept`` returns its
    first validated origin winner without renewing the stored proposal. ``submit``
    retains exact logical matching. Neither method invokes or delivers work.
    """

    def __init__(
        self,
        *,
        executions: TaskExecutionPort,
        scope: Scope,
        case_authority: CaseAuthorityPort,
        max_active: int = 4,
        timeout_ms: int = 5000,
        cleanup_ms: int = 1000,
    ) -> None:
        super().__init__(
            executions=executions,
            codec=CHANNEL_CODEC,
            scope=scope,
            case_authority=case_authority,
            max_active=max_active,
            timeout_ms=timeout_ms,
            cleanup_ms=cleanup_ms,
        )

    @property
    def scope(self) -> Scope:
        """Configured immutable scope for composition checks; no authority observation."""
        return self._scope

    async def submit(self, request: ChannelPolicyRequest) -> ChannelPolicySubmission:
        value = await self._submit_request(request)
        return ChannelPolicySubmission(
            ChannelPolicyView(value.view.record, value.view.request), value.created
        )

    async def accept(self, request: ChannelPolicyRequest) -> ChannelPolicySubmission:
        value = await self._submit_request(request, identity="channel_origin")
        return ChannelPolicySubmission(
            ChannelPolicyView(value.view.record, value.view.request), value.created
        )

    async def find(self, delegation_id: str) -> ChannelPolicyView | None:
        value = await self._find_request(delegation_id)
        return None if value is None else ChannelPolicyView(value.record, value.request)

    async def get(self, work_id: str) -> ChannelPolicyView:
        value = await self._get_request(work_id)
        return ChannelPolicyView(value.record, value.request)

    async def get_many(self, work_ids: tuple[str, ...]) -> dict[str, ChannelPolicyView]:
        """Read an as-of page of accepted work; invocation still checks current authority."""
        if type(work_ids) is not tuple or not 1 <= len(work_ids) <= 16:
            raise CoordinatorError("invalid_input")
        requested = {_uuid(work_id) for work_id in work_ids}
        if len(requested) != len(work_ids):
            raise CoordinatorError("invalid_input")

        async def read(_call: _Call) -> dict[str, ChannelPolicyView]:
            source = self._executions
            if isinstance(source, _BatchWorkReader):
                records = await source.get_many(work_ids=work_ids)
            else:
                records = {}
                for work_id in work_ids:
                    self._check(_call)
                    records[work_id] = await source.get(work_id=work_id)
            if type(records) is not dict or not records.keys() <= requested:
                raise CoordinatorError("invalid_stored_state")
            result = {}
            for work_id, record in records.items():
                view = self._view(record)
                if view.record.work_id != work_id:
                    raise CoordinatorError("invalid_stored_state")
                result[work_id] = ChannelPolicyView(view.record, view.request)
            return result

        return await self._run("get", read)


class ChannelPolicyRunner(_RunnerCore[ChannelPolicyRequest, ChannelPolicyResult]):
    """Issue v3 history while the explicit specialist adapter speaks only v2.

    Own the execution and specialist ports. Original source records and the case
    authority remain application composition; first-origin replay does not select
    a newer source configuration for execution.
    """

    def __init__(
        self,
        *,
        executions: ExecutionPort,
        scope: Scope,
        owner_id: str,
        specialist: FixedPolicyInvocationPort,
        case_authority: CaseAuthorityPort,
        evidence: tuple[EvidenceRecord, ...],
        max_active: int = 1,
        timeout_ms: int = 5000,
        cleanup_ms: int = 1000,
        recover_expired: bool = False,
    ) -> None:
        try:
            if (
                type(evidence) is not tuple
                or len(evidence) != 2
                or type(recover_expired) is not bool
            ):
                raise ContractError()
            copied = _snapshot_fixed_policy_pair(evidence)
            if any(
                item.reference.media_type != "application/json" or len(item.body) > 4096
                for item in copied
            ):
                raise ContractError()
        except (ContractError, AttributeError, TypeError, ValueError):
            raise DelegationRunError("invalid_input") from None
        self._recover_expired = recover_expired
        super().__init__(
            executions=executions,
            codec=CHANNEL_CODEC,
            scope=scope,
            owner_id=owner_id,
            specialist=_ChannelInvocation(specialist, copied),
            case_authority=case_authority,
            evidence=copied,
            max_active=max_active,
            timeout_ms=timeout_ms,
            cleanup_ms=cleanup_ms,
        )

    async def run_once(self, work_id: str, command_id: str) -> ChannelPolicyRun:
        value = await self._run_once_request(
            work_id, command_id, recover_expired=self._recover_expired
        )
        view = value.view
        return ChannelPolicyRun(
            ChannelPolicyExecutionView(
                view.execution, view.request, view.result, view.applicability
            ),
            value.invoked,
            value.recorded,
        )

    async def inspect(self, work_id: str) -> ChannelPolicyExecutionView:
        value = await self._inspect_request(work_id)
        return ChannelPolicyExecutionView(
            value.execution, value.request, value.result, value.applicability
        )
