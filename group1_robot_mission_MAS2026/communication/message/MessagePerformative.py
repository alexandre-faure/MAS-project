#!/usr/bin/env python3

from enum import Enum


class MessagePerformative(Enum):
    PROPOSE_TO_GIVE = 101.1
    PROPOSE_TO_TAKE = 101.2

    ACCEPT_EXCHANGE = 102.1
    REJECT_EXCHANGE = 103.1

    COMMIT = 103
    ASK_WHY = 104
    ARGUE = 105
    QUERY_REF = 106
    INFORM_REF = 107
    INFORM_DROP = 108       
    INFORM_PICKUP = 109      
    def __str__(self):
        return '{0}'.format(self.name)
