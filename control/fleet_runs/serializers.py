from typing import Any

from rest_framework import serializers

from .models import Run, RunStep


class RunSerializer(serializers.ModelSerializer[Run]):
    class Meta:
        model = Run
        fields = [
            "id",
            "state",
            "trigger_kind",
            "input_text",
            "error",
            "cost_microusd_total",
            "tokens_in_total",
            "tokens_out_total",
            "created_at",
            "started_at",
            "ended_at",
        ]


class RunStepSerializer(serializers.ModelSerializer[RunStep]):
    class Meta:
        model = RunStep
        fields = [
            "step_index",
            "kind",
            "provider",
            "tokens_in",
            "tokens_out",
            "cost_microusd",
            "price_table_version",
            "duration_ms",
            "created_at",
        ]


class RunStepWithPayloadsSerializer(RunStepSerializer):
    class Meta(RunStepSerializer.Meta):
        fields = RunStepSerializer.Meta.fields + [
            "request_payload",
            "response_payload",
            "rng_seed",
            "clock_reads",
        ]


class CreateRunRequestSerializer(serializers.Serializer[Any]):
    input = serializers.CharField(allow_blank=True, default="", trim_whitespace=False)
