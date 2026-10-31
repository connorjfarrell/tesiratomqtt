"""Mixer input/output mute and delay controls."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from conftest import wait_until
from errors import ClientError
from fake_tesira import Block
from models import ATTRIBUTES, Subscription, subscription_identifier

if TYPE_CHECKING:
    from fake_mqtt import FakeMqtt
    from fake_tesira import FakeTesiraServer
    from tesira import BiampTesiraConnection


def _sub(tag: str, attribute: str, index: int = 1) -> Subscription:
    return Subscription(
        instance_tag=tag,
        attribute=attribute,  # type: ignore[arg-type]
        index=index,
        name=attribute,
        device_name="Room",
    )


def test_registry_matches_the_accepted_attributes() -> None:
    accepted = Subscription.model_fields["attribute"].annotation.__args__
    assert set(accepted) == set(ATTRIBUTES)


async def test_delay_is_a_polled_read_only_value(
    connection: BiampTesiraConnection, server: FakeTesiraServer, mqtt: FakeMqtt
) -> None:
    server.blocks["Dly"] = Block(delay=5.634)
    identifier = subscription_identifier("Dly", "delay", 1)
    await connection.open()
    await connection.subscribe(_sub("Dly", "delay"))

    assert "Dly get delay" in server.commands_received
    assert not any("subscribe" in c for c in server.commands_received if "Dly" in c)
    await wait_until(lambda: mqtt.states_for(identifier)[-1:] == [5.634])
    entry = connection._subscriptions[identifier]
    assert entry["read_only"] is True
    assert entry["unit"] == "ms"
    assert "min_level" not in entry

    with pytest.raises(ClientError, match="read-only"):
        await connection.update_state_and_command(identifier, "12.5")
    assert not any(" set " in c for c in server.commands_received)

    # A refresh picks up a change made elsewhere.
    server.blocks["Dly"].delay = 7.0
    await connection.subscribe(_sub("Dly", "delay"))
    await wait_until(lambda: mqtt.states_for(identifier)[-1:] == [7.0])


async def test_input_mute_is_indexed(
    connection: BiampTesiraConnection, server: FakeTesiraServer
) -> None:
    server.blocks["Mix"] = Block()
    identifier = subscription_identifier("Mix", "inputMute", 2)
    await connection.open()
    await connection.subscribe(_sub("Mix", "inputMute", 2))

    assert f"Mix subscribe inputMute 2 {identifier}" in server.commands_received
    await connection.update_state_and_command(identifier, "true")
    assert "Mix set inputMute 2 true" in server.commands_received
    assert server.blocks["Mix"].input_mute is True


async def test_output_mute_is_unindexed(
    connection: BiampTesiraConnection, server: FakeTesiraServer
) -> None:
    server.blocks["Mix"] = Block()
    identifier = subscription_identifier("Mix", "outputMute", 1)
    await connection.open()
    await connection.subscribe(_sub("Mix", "outputMute"))

    assert f"Mix subscribe outputMute {identifier}" in server.commands_received
    await connection.update_state_and_command(identifier, "true")
    assert "Mix set outputMute true" in server.commands_received


def test_unknown_attribute_is_rejected() -> None:
    with pytest.raises(ValueError, match="attribute"):
        _sub("Mix", "inputGain")
