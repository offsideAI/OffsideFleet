"""Runner-gateway configuration (env-driven)."""

from dataclasses import dataclass, field

from environs import Env

env = Env()
env.read_env()


@dataclass(frozen=True)
class GatewayConfig:
    internal_api_secret: str = field(
        default_factory=lambda: env.str("FLEET_INTERNAL_API_SECRET", default="dev-internal-secret")
    )
    agent_image: str = field(
        default_factory=lambda: env.str("FLEET_AGENT_IMAGE", default="offsidefleet-agent:dev")
    )
    # Docker network the agent containers join. Must be an *internal* network
    # (no default route); the egress proxy is its only way out.
    agent_network: str = field(
        default_factory=lambda: env.str("FLEET_AGENT_NETWORK", default="fleet_internal")
    )
    egress_proxy_url: str = field(
        default_factory=lambda: env.str(
            "FLEET_EGRESS_PROXY_URL", default="http://fleet-egress-proxy:8888"
        )
    )
    # URL at which the control plane is reachable *from inside an agent
    # container via the proxy* (dev: host.docker.internal).
    control_plane_url: str = field(
        default_factory=lambda: env.str(
            "FLEET_CONTROL_PLANE_URL", default="http://host.docker.internal:8000"
        )
    )
    # Model reverse-proxy (egress service): terminates TLS at our proxy and
    # injects the Anthropic key there — the key never enters agent containers.
    model_proxy_url: str = field(
        default_factory=lambda: env.str(
            "FLEET_MODEL_PROXY_URL", default="http://fleet-egress-proxy:8889"
        )
    )
    run_timeout_seconds: int = field(
        default_factory=lambda: env.int("FLEET_RUN_TIMEOUT_SECONDS", default=900)
    )
    mem_limit: str = field(default_factory=lambda: env.str("FLEET_RUN_MEM_LIMIT", default="512m"))
    pids_limit: int = field(default_factory=lambda: env.int("FLEET_RUN_PIDS_LIMIT", default=64))
    nano_cpus: int = field(
        default_factory=lambda: env.int("FLEET_RUN_NANO_CPUS", default=1_000_000_000)
    )


config = GatewayConfig()
