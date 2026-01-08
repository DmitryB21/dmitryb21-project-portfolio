"""FSM состояния"""

from .task_states import TaskAddStates
from .deal_states import DealAddStates, DealChangeStatusStates
from .marketing_states import MarketingAdviceStates

__all__ = ["TaskAddStates", "DealAddStates", "DealChangeStatusStates", "MarketingAdviceStates"]

