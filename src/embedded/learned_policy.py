from common.policy import Policy

WEIGHTS_PATH = "model_weights.bin"  # placeholder; format TBD when training is wired up


class LearnedPolicy(Policy):
    """Stub for an emlearn-backed inference policy.

    When implemented (Bridge A: PyTorch DQN -> sklearn MLPRegressor -> emlearn export),
    this class will load WEIGHTS_PATH on construction and run inference each tick.

    Today it raises so a misconfigured POLICY constant fails loudly at startup
    rather than silently falling back.
    """

    def __init__(self):
        raise NotImplementedError("LearnedPolicy is not implemented yet. Set POLICY = 'greedy' in embedded/main.py.")

    def decide(self, engine):
        raise NotImplementedError
