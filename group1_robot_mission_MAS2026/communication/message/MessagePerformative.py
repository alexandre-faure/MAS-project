#!/usr/bin/env python3

from enum import Enum


class MessagePerformative(Enum):
    """MessagePerformative enum class.
    Enumeration containing the possible message performative.
    """
    PROPOSE_TO_GIVE = 101.1
    PROPOSE_TO_TAKE = 101.2   
    
    ACCEPT_EXCHANGE = 102.1
    REJECT_EXCHANGE = 103.1

    COMMIT = 103
    ASK_WHY = 104
    ARGUE = 105
    QUERY_REF = 106
    INFORM_REF = 107

    def __str__(self):
        """Returns the name of the enum item.
        """
        return '{0}'.format(self.name)
