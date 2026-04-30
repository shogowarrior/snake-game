import matplotlib.pyplot as plt
from IPython import display

plt.ion()

# Create a figure with a specific size
plt.figure(figsize=(4, 2))  # Width = 10 inches, Height = 6 inches


def plot(scores, mean_scores, mva_score):
    display.clear_output(wait=True)
    display.display(plt.gcf())
    plt.clf()
    plt.title("Scores chart")
    plt.xlabel("Number of Games")
    plt.ylabel("Score")
    plt.plot(scores, label="Score", alpha=0.3)
    plt.plot(mean_scores, label="Mean Score", alpha=0.3)
    plt.plot(mva_score, label="MVA Score", alpha=0.3)
    plt.ylim(ymin=0)
    plt.text(len(scores) - 1, scores[-1], str(scores[-1]))
    plt.text(len(mean_scores) - 1, mean_scores[-1], str(mean_scores[-1]))
    plt.text(len(mva_score) - 1, mva_score[-1], str(mva_score[-1]))
    plt.figlegend()
    plt.show(block=False)
    plt.pause(0.1)
