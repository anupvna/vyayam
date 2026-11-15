"""The deterministic engine: pure functions, no database or HTTP.

Everything here is plain input -> output, which is what makes it easy to test
exhaustively (including property-based tests) and to reuse when validating the AI
coach's suggestions.
"""
