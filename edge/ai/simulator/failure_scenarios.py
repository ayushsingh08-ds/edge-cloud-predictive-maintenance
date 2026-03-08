class FailureScenario:

    def __init__(self, name, mode, duration_minutes):
        self.name = name
        self.mode = mode
        self.duration_minutes = duration_minutes

    def duration_seconds(self):
        return self.duration_minutes * 60


SCENARIOS = [

    FailureScenario(
        name="Normal Operation",
        mode="normal",
        duration_minutes=30
    ),

    FailureScenario(
        name="Gradual Bearing Wear",
        mode="degrading",
        duration_minutes=60
    ),

    FailureScenario(
        name="Sudden Overload",
        mode="failing",
        duration_minutes=10
    )

]