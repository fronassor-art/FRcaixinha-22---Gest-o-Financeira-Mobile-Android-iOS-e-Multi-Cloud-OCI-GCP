"""FR Finance — observador somente leitura da instancia OCI A1 para GitHub Actions.

Nao chama criacao, atualizacao ou exclusao de recursos. Nenhum OCID ou
segredo e gravado nos logs; M28619 no Termux permanece o unico criador.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import sys

REGION = "sa-saopaulo-1"
VM_NAME = "fr-finance-a1-always-free"
SHAPE = "VM.Standard.A1.Flex"
LIFECYCLE_EXPECTED = {
    "PROVISIONING", "STARTING", "RUNNING", "STOPPING", "STOPPED",
    "MOVING", "CREATING_IMAGE",
}


def report(status: str, found: bool, detail: str) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(
        f"{timestamp} OCI_A1_MONITOR={status} "
        f"VM_FOUND={'YES' if found else 'NO'} {detail}"
    )
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as file:
            file.write(f"vm_found={'true' if found else 'false'}\n")
            file.write(f"vm_state={status}\n")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as file:
            file.write("## FR Finance — observador OCI A1\n")
            file.write(f"- Consulta UTC: {timestamp}\n")
            file.write(f"- Regiao: {REGION}\n")
            file.write(f"- Instancia encontrada: {'sim' if found else 'nao'}\n")
            file.write(f"- Estado: **{status}**\n")
            file.write(f"- Resultado: {detail}\n")
            file.write("- Nenhuma VM criada, modificada ou excluida por esta rotina.\n")


def run() -> int:
    try:
        import oci

        config = {
            "user": os.environ["FRF_OCI_USER_OCID"],
            "tenancy": os.environ["FRF_OCI_TENANCY_OCID"],
            "fingerprint": os.environ["FRF_OCI_FINGERPRINT"],
            "key_file": os.environ["FRF_OCI_KEY_PATH"],
            "region": REGION,
        }
        if not Path(config["key_file"]).is_file():
            raise ValueError("Signing key missing")
        oci.config.validate_config(config)
        identity = oci.identity.IdentityClient(config)
        compute = oci.core.ComputeClient(config)
        tenancy = config["tenancy"]
        children = oci.pagination.list_call_get_all_results(
            identity.list_compartments,
            tenancy,
            compartment_id_in_subtree=True,
            access_level="ACCESSIBLE",
        ).data
        compartments = [tenancy] + [
            child.id for child in children if child.lifecycle_state == "ACTIVE"
        ]
        if len(compartments) > 100:
            raise ValueError("Too many compartments")

        matches = []
        for compartment_id in dict.fromkeys(compartments):
            instances = oci.pagination.list_call_get_all_results(
                compute.list_instances, compartment_id
            ).data
            for instance in instances:
                if (
                    instance.display_name == VM_NAME
                    and instance.lifecycle_state != "TERMINATED"
                ):
                    matches.append(instance.id)

        if not matches:
            report("NOT_FOUND", False, "Termux continua responsavel pela criacao")
            return 0
        if len(matches) != 1:
            report("REVIEW_REQUIRED", False, "Mais de uma VM com o nome esperado")
            return 2

        vm = compute.get_instance(matches[0]).data
        shape_config = getattr(vm, "shape_config", None)
        if (
            vm.shape != SHAPE
            or shape_config is None
            or float(shape_config.ocpus) != 2.0
            or float(shape_config.memory_in_gbs) != 12.0
        ):
            report("REVIEW_REQUIRED", False, "Shape ou capacidade diverge do aprovado")
            return 2

        if vm.lifecycle_state not in LIFECYCLE_EXPECTED:
            report("REVIEW_REQUIRED", True, "Ciclo de vida incomum; revisar console")
            return 2

        report(vm.lifecycle_state, True, "A1 Flex 2 OCPU 12 GB detectada")
        return 0

    except KeyError:
        report("MONITOR_ERROR", False, "Credencial GitHub ausente")
        return 3
    except Exception as exc:
        # Evita imprimir mensagens de erro contendo identificadores e headers.
        report("MONITOR_ERROR", False, f"Falha OCI: {type(exc).__name__}")
        return 3


if __name__ == "__main__":
    sys.exit(run())
