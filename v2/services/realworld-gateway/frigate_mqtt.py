import json
import logging
from typing import Callable, Optional

from paho.mqtt import client as mqtt

log = logging.getLogger("frigate-mqtt")


class FrigateSubscriber:
    """
    Lightweight MQTT subscriber for Frigate event notifications.

    The subscriber uses the paho async loop in a background thread and invokes
    the provided callback whenever a message arrives on the watched topic.
    """

    def __init__(
        self,
        broker: str = "127.0.0.1",
        topic: str = "frigate/events",
        on_event: Optional[Callable[[dict], None]] = None,
    ) -> None:
        self.broker = broker
        self.topic = topic
        self.on_event = on_event
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="realworld-gateway",
            clean_session=True,
        )
        self._client.enable_logger(log)

    def start(self) -> None:
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.connect(self.broker, 1883, keepalive=60)
        self._client.loop_start()
        log.info("Frigate MQTT subscriber started (broker=%s topic=%s)", self.broker, self.topic)

    def stop(self) -> None:
        try:
            self._client.loop_stop()
            self._client.disconnect()
        except Exception:
            pass

    def _on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        if reason_code == 0:
            log.info("MQTT connected (rc=%s)", reason_code)
        else:
            log.warning("MQTT connection issue (rc=%s)", reason_code)
        client.subscribe(self.topic)

    def _on_message(self, client, userdata, msg) -> None:
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except Exception as exc:
            log.exception("Unable to decode Frigate MQTT payload: %s", exc)
            return

        if self.on_event:
            try:
                self.on_event(payload)
            except Exception as exc:
                log.exception("MQTT on_event handler raised: %s", exc)
