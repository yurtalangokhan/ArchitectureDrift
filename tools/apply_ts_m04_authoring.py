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

    count = text.count(
        old_normalized
    )

    if count != 1:
        raise RuntimeError(
            f"Expected exactly one replacement in {path}, "
            f"found {count}"
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
            "python tools/apply_ts_m04_authoring.py "
            "<authoring-worktree>"
        )

    workspace = Path(
        sys.argv[1]
    ).resolve()

    image_path = (
        workspace
        / "services"
        / "tools.descartes.teastore.image"
        / "src"
        / "main"
        / "java"
        / "tools"
        / "descartes"
        / "teastore"
        / "image"
        / "rest"
        / "ImageProviderEndpoint.java"
    )

    replace_once(
        image_path,
        """import java.util.HashMap;
import java.util.stream.Collectors;
""",
        """import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.HashMap;
import java.util.stream.Collectors;
""",
    )

    replace_once(
        image_path,
        """public class ImageProviderEndpoint {

""",
        """public class ImageProviderEndpoint {

  private static final String TS_M04_TRIGGER_ENV =
      "ARCHDRIFT_TS_M04_TRIGGER";

  private static final String TS_M04_RECOMMENDER_URL =
      "http://recommender:8080/"
      + "tools.descartes.teastore.recommender/"
      + "rest/train/isready";

  private static void invokeTSM04RecommenderIfEnabled() {
    if (!"true".equalsIgnoreCase(
        System.getenv(TS_M04_TRIGGER_ENV))) {
      return;
    }

    HttpURLConnection connection = null;

    try {
      URL url = new URL(
          TS_M04_RECOMMENDER_URL);

      connection =
          (HttpURLConnection) url.openConnection();

      connection.setRequestMethod("GET");
      connection.setConnectTimeout(1000);
      connection.setReadTimeout(1000);
      connection.getResponseCode();

    } catch (IOException ignored) {
      // The controlled mutation must not alter
      // Image service business behavior.

    } finally {
      if (connection != null) {
        connection.disconnect();
      }
    }
  }

""",
    )

    replace_once(
        image_path,
        """  public Response getState() {
    return Response.ok().entity(SetupController.SETUP.getState()).build();
  }
""",
        """  public Response getState() {
    invokeTSM04RecommenderIfEnabled();
    return Response.ok().entity(SetupController.SETUP.getState()).build();
  }
""",
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())