from unittest import TestCase
from io import StringIO
from roborescue import plan_decoder
from roborescue.action import Move, Rescue, Load, Unload, Unblock, Clear


class TestPlanDecoder(TestCase):

    plan_string = """0.000: (unblock police1 hospital1 building1)  [10.000]
10.000: (clear hospital1 building1 cleared-hospital1-building1-0)  [0.000]
10.001: (move medic1 hospital1 building1)  [50.000]
60.002: (rescue medic1 civ2 building1)  [100.000]
160.003: (rescue medic1 civ1 building1)  [100.000]
260.003: (load medic1 civ2 building1)  [1.000]
261.003: (move medic1 building1 hospital1)  [50.000]
311.003: (unload medic1 civ2 hospital1)  [1.000]
312.003: (move medic1 hospital1 building1)  [50.000]
362.003: (load medic1 civ1 building1)  [1.000]
363.003: (move medic1 building1 hospital1)  [50.000]
413.003: (unload medic1 civ1 hospital1)  [1.000]

"""

    def test_decode_plan(self):
        # given
        in_ = StringIO(self.plan_string)
        expected = [
            Unblock(0, 10, "police1", "hospital1", "building1"),
            # Clear(10, 0, "hospital1", "building1", "cleared-hospital1-building1-0"), <-- should not appear
            Move(10, 50, "medic1", "hospital1", "building1"),
            Rescue(60, 100, "medic1", "civ2", "building1"),
            Rescue(160, 100, "medic1", "civ1", "building1"),
            Load(260, 1, "medic1", "civ2", "building1"),
            Move(261, 50, "medic1", "building1", "hospital1"),
            Unload(311, 1, "medic1", "civ2", "hospital1"),
            Move(312, 50, "medic1", "hospital1", "building1"),
            Load(362, 1, "medic1", "civ1", "building1"),
            Move(363, 50, "medic1", "building1", "hospital1"),
            Unload(413, 1, "medic1", "civ1", "hospital1"),
        ]

        # when
        plan = list(plan_decoder.decode_plan(in_, time=0))

        # then
        self.assertEqual(expected, plan)
