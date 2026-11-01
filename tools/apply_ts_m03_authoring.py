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
            "python tools/apply_ts_m03_authoring.py "
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

    recommender_path = (
        workspace
        / "services"
        / "tools.descartes.teastore.recommender"
        / "src"
        / "main"
        / "java"
        / "tools"
        / "descartes"
        / "teastore"
        / "recommender"
        / "rest"
        / "RecommendEndpoint.java"
    )

    replace_once(
        compose_path,
        """  recommender:
    image: descartesresearch/teastore-recommender
    expose:
      - "8080"
    environment:
      HOST_NAME: "recommender"
      REGISTRY_HOST: "registry"
""",
        """  recommender:
    image: descartesresearch/teastore-recommender
    expose:
      - "8080"
    environment:
      HOST_NAME: "recommender"
      REGISTRY_HOST: "registry"
      AUTH_ADDR: "auth"
""",
    )

    replace_once(
        recommender_path,
        """import java.util.List;
""",
        """import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.List;
""",
    )

    replace_once(
        recommender_path,
        """public class RecommendEndpoint {

""",
        """public class RecommendEndpoint {

    private static final String TS_M03_AUTH_ADDR_ENV =
            "AUTH_ADDR";

    private static final String TS_M03_AUTH_PATH =
            "/tools.descartes.teastore.auth/rest/ready/isready";

    private static void invokeTSM03Authentication() {
        String authHost =
                System.getenv(TS_M03_AUTH_ADDR_ENV);

        if (authHost == null
                || authHost.trim().isEmpty()) {
            return;
        }

        HttpURLConnection connection = null;

        try {
            URL url = new URL(
                    "http://"
                            + authHost
                            + ":8080"
                            + TS_M03_AUTH_PATH);

            connection =
                    (HttpURLConnection) url.openConnection();

            connection.setRequestMethod("GET");
            connection.setConnectTimeout(1000);
            connection.setReadTimeout(1000);
            connection.getResponseCode();

        } catch (IOException ignored) {
            // The controlled mutation must not alter
            // recommendation business behavior.

        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }

""",
    )

    replace_once(
        recommender_path,
        """\tpublic Response recommend(List<OrderItem> currentItems, @QueryParam("uid") final Long uid) {
\t\tList<Long> recommended = RecommenderSelector.getInstance().recommendProducts(uid, currentItems);
""",
        """\tpublic Response recommend(List<OrderItem> currentItems, @QueryParam("uid") final Long uid) {
\t\tinvokeTSM03Authentication();
\t\tList<Long> recommended = RecommenderSelector.getInstance().recommendProducts(uid, currentItems);
""",
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())