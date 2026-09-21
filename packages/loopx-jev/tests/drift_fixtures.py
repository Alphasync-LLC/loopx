"""Explicitly injected model answers; not provider quality evidence."""


def response(request, choices=None):
    answers = {}
    for index, (name, question) in enumerate(request["questions"].items()):
        labels = list(question["criteria"])
        selected = choices[index] if choices else labels[0]
        answers[name] = {
            "type": "choice",
            "choice": selected,
            "confidence": 1.0,
            "probabilities": {label: float(label == selected) for label in labels},
        }
    return {"model": request["model"], "answers": answers}
