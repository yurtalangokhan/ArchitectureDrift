from __future__ import annotations

import sys
from pathlib import Path


def replace_once(
    path: Path,
    old: str,
    new: str,
) -> None:
    raw = path.read_bytes()
    text = raw.decode("utf-8")

    newline = (
        "\r\n"
        if "\r\n" in text
        else "\n"
    )

    old_normalized = old.replace(
        "\n",
        newline,
    )
    new_normalized = new.replace(
        "\n",
        newline,
    )

    if text.count(old_normalized) != 1:
        raise RuntimeError(
            "Expected exactly one replacement "
            f"in {path}, found "
            f"{text.count(old_normalized)}"
        )

    updated = text.replace(
        old_normalized,
        new_normalized,
        1,
    )

    path.write_bytes(
        updated.encode("utf-8")
    )


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: "
            "python tools/apply_ts_m02_authoring.py "
            "<authoring-worktree>"
        )

    workspace = Path(
        sys.argv[1]
    ).resolve()

    compose_path = (
        workspace
        / "examples"
        / "docker"
        / "docker-compose_default.yaml"
    )

    auth_path = (
        workspace
        / "services"
        / "tools.descartes.teastore.auth"
        / "src"
        / "main"
        / "java"
        / "tools"
        / "descartes"
        / "teastore"
        / "auth"
        / "rest"
        / "AuthUserActionsRest.java"
    )

    replace_once(
        compose_path,
        """  auth:
    image: descartesresearch/teastore-auth
    expose:
      - "8080"
    environment:
      HOST_NAME: "auth"
      REGISTRY_HOST: "registry"
""",
        """  auth:
    image: descartesresearch/teastore-auth
    expose:
      - "8080"
    environment:
      HOST_NAME: "auth"
      REGISTRY_HOST: "registry"
      IMAGE_ADDR: "image"
""",
    )

    replace_once(
        auth_path,
        """import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
""",
        """import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.URL;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
""",
    )

    replace_once(
        auth_path,
        """public class AuthUserActionsRest {

""",
        """public class AuthUserActionsRest {

  private static final String TS_M02_TRIGGER_ENV =
      "ARCHDRIFT_TS_M02_TRIGGER";

  private static final String TS_M02_IMAGE_ADDR_ENV =
      "IMAGE_ADDR";

  private static final String TS_M02_IMAGE_PATH =
      "/tools.descartes.teastore.image/rest/image/finished";

  private static void invokeTSM02ImageIfEnabled() {
    if (!"true".equalsIgnoreCase(
        System.getenv(TS_M02_TRIGGER_ENV))) {
      return;
    }

    String imageHost =
        System.getenv(TS_M02_IMAGE_ADDR_ENV);

    if (imageHost == null
        || imageHost.trim().isEmpty()) {
      return;
    }

    HttpURLConnection connection = null;

    try {
      URL url = new URL(
          "http://"
              + imageHost
              + ":8080"
              + TS_M02_IMAGE_PATH);

      connection =
          (HttpURLConnection) url.openConnection();

      connection.setRequestMethod("GET");
      connection.setConnectTimeout(1000);
      connection.setReadTimeout(1000);
      connection.getResponseCode();

    } catch (IOException ignored) {
      // Mutation probe must not alter
      // Authentication business outcome.

    } finally {
      if (connection != null) {
        connection.disconnect();
      }
    }
  }

""",
    )

    replace_once(
        auth_path,
        """  public Response login(SessionBlob blob, @QueryParam("name") String name,
      @QueryParam("password") String password) {
    User user;
""",
        """  public Response login(SessionBlob blob, @QueryParam("name") String name,
      @QueryParam("password") String password) {
    invokeTSM02ImageIfEnabled();

    User user;
""",
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())