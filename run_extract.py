from agent import Agent


def main():
    # Create an Agent instance without invoking __init__ to avoid side effects
    agent = object.__new__(Agent)

    tests = [
        "I'll pay the full amount",
        "I'll pay 500 for now",
        "pay five hundred rupees",
    ]

    for t in tests:
        try:
            result = Agent._extract_amount(agent, t)
        except Exception as e:
            result = f"Exception: {e!r}"
        print(f"Input: {t!r} -> {result!r}")


if __name__ == '__main__':
    main()
