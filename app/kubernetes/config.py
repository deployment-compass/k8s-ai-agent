from pathlib import Path

from kubernetes import config as k8s_config

from app.config import settings


def load_kubernetes_config() -> None:
    try:
        k8s_config.load_incluster_config()
    except k8s_config.ConfigException:
        kubeconfig_path = settings.kubeconfig_file
        if kubeconfig_path.exists():
            k8s_config.load_kube_config(config_file=str(kubeconfig_path))
        else:
            k8s_config.load_kube_config()
