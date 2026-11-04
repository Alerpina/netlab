*** Settings ***
Documentation       Post-checks: a rede ficou como o NetBox diz que deve ficar.
Library             netauto.robot_lib.NetautoLibrary    ${INTENT_DIR}


*** Variables ***
${INTENT_DIR}       build/intents


*** Test Cases ***
Interfaces da fábrica estão up
    ${hosts}=    Get Lab Hosts
    FOR    ${host}    IN    @{hosts}
        Wait Until Keyword Succeeds    60s    5s    Interfaces Should Be Up    ${host}
    END

Cabeamento confere com o NetBox (LLDP)
    ${hosts}=    Get Lab Hosts
    FOR    ${host}    IN    @{hosts}
        Wait Until Keyword Succeeds    90s    10s    LLDP Neighbors Should Match Source Of Truth    ${host}
    END

Running igual à intenção (sem drift)
    ${hosts}=    Get Lab Hosts
    FOR    ${host}    IN    @{hosts}
        Configuration Should Have No Drift    ${host}
    END
