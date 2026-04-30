class Policy:
    """Picks the next direction given the current engine state.

    Implementations:
      - embedded.greedy_policy.GreedyPolicy   — wrapped-distance greedy
      - embedded.learned_policy.LearnedPolicy — stub today; emlearn-backed later
      - desktop.main.Agent                    — DQN; conforms but isn't swapped at runtime
    """

    def decide(self, engine):
        """Return a Direction.* value, or None to keep the current heading."""
        raise NotImplementedError
