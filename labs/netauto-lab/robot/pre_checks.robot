*** Settings ***
Documentation       Pre-checks: o que precisa ser verdade antes de qualquer mudança.
Library             netauto.robot_lib.NetautoLibrary    ${INTENT_DIR}


*** Variables ***
${INTENT_DIR}       build/intents


*** Test Cases ***
Intenção gerada para todos os equipamentos
    ${hosts}=    Get Lab Hosts
    Should Not Be Empty    ${hosts}    Nenhuma intenção em ${INTENT_DIR}: rode o render

Equipamentos respondem via JSON-RPC
    ${hosts}=    Get Lab Hosts
    FOR    ${host}    IN    @{hosts}
        ${version}=    Device Should Be Reachable    ${host}
        Log    ${host}: SR Linux ${version}
    END
