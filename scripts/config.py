import yaml
from argparse import ArgumentParser

# these project-specific values are loaded from the --config YAML
_project_path = ""
_samples = {}
_custom_samples = {}
_artifact_names = {}
_artifact_paths = {}
_artifact_prefix = ""
_dict = {}

_loaded = False


def load(config_path=None):
    global _dict
    if config_path is None:
        ap = ArgumentParser()
        ap.add_argument("-c", "--config", required=True)
        args, _ = ap.parse_known_args()
        config_path = args.config

    with open(config_path) as f:
        config = yaml.safe_load(f)
    _dict = config

    for key in config:
        hidden_key = "_" + key
        if hidden_key in globals():
            globals()[hidden_key] = config[key]

    for artifact_name, artifact_path in _artifact_names.items():
        _artifact_paths[artifact_name] = _artifact_prefix + artifact_path

    # Also expose this computed key in the dict for completeness
    _dict["artifact_paths"] = _artifact_paths

    global _loaded
    _loaded = True


def __getattr__(name):
    if not _loaded:
        raise ValueError(f"Tried to get config attribute {name} without loaded config")

    attr = globals().get("_" + name, None)
    if attr is None:
        raise AttributeError(name)
    return attr
