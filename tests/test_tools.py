"""
tests/test_tools.py - Strategy Pattern Hardware Tools & Simulator Tests.
"""

from tools.registry import ToolRegistry
from tools.hardware import BatteryStatusStrategy, TorchControlStrategy, VibrateDeviceStrategy
from tools.telephony import SendSmsStrategy, MakeCallStrategy
from tools.system import ShowToastStrategy, SetClipboardStrategy, GetClipboardStrategy


def test_tool_registry_registration():
    reg = ToolRegistry()
    assert reg.get("get_battery_status") is not None
    assert reg.get("set_torch") is not None
    assert reg.get("send_sms") is not None
    assert reg.get("non_existent_tool") is None


def test_battery_strategy_execution():
    strat = BatteryStatusStrategy()
    res = strat.run_safe()
    assert res.success is True
    assert res.output is not None
    # Simulator returns dictionary with percentage
    if isinstance(res.output, dict):
        assert "percentage" in res.output


def test_torch_strategy_execution():
    strat = TorchControlStrategy()
    res_on = strat.run_safe(on=True)
    assert res_on.success is True

    res_off = strat.run_safe(on=False)
    assert res_off.success is True


def test_sms_strategy_execution():
    strat = SendSmsStrategy()
    # Valid phone
    res = strat.run_safe(recipient="+1234567890", message="Hello from unit test")
    assert res.success is True

    # Malicious injection phone must fail gracefully with error
    res_bad = strat.run_safe(recipient="+1234; rm -rf /", message="Injection attempt")
    assert res_bad.success is False
    assert "Security violation" in str(res_bad.error) or "Invalid phone" in str(res_bad.error)
