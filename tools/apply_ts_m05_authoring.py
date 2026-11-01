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
            "python tools/apply_ts_m05_authoring.py "
            "<authoring-worktree>"
        )

    workspace = Path(
        sys.argv[1]
    ).resolve()

    user_endpoint = (
        workspace
        / "services"
        / "tools.descartes.teastore.persistence"
        / "src"
        / "main"
        / "java"
        / "tools"
        / "descartes"
        / "teastore"
        / "persistence"
        / "rest"
        / "UserEndpoint.java"
    )

    replace_once(
        user_endpoint,
        """import java.util.ArrayList;
import java.util.List;
""",
        """import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;
import java.util.List;
""",
    )

    replace_once(
        user_endpoint,
        """public class UserEndpoint extends AbstractCRUDEndpoint<User> {

""",
        """public class UserEndpoint extends AbstractCRUDEndpoint<User> {

    private static final String TS_M05_AUTH_URL =
            "http://auth:8080/"
            + "tools.descartes.teastore.auth/"
            + "rest/ready/isready";

    private static void invokeTSM05Authentication() {
        HttpURLConnection connection = null;

        try {
            URL url = new URL(
                    TS_M05_AUTH_URL);

            connection =
                    (HttpURLConnection) url.openConnection();

            connection.setRequestMethod("GET");
            connection.setConnectTimeout(1000);
            connection.setReadTimeout(1000);
            connection.getResponseCode();

        } catch (IOException ignored) {
            // The controlled mutation must not alter
            // Persistence business behavior.

        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }

""",
    )

    replace_once(
        user_endpoint,
        """\tpublic Response findById(@PathParam("name") final String name) {
\t\tif (name == null || name.isEmpty()) {
\t\t\treturn Response.status(Status.NOT_FOUND).build();
\t\t}
\t\tUser entity = UserRepository.REPOSITORY.getUserByName(name);
""",
        """\tpublic Response findById(@PathParam("name") final String name) {
\t\tif (name == null || name.isEmpty()) {
\t\t\treturn Response.status(Status.NOT_FOUND).build();
\t\t}

\t\tinvokeTSM05Authentication();

\t\tUser entity = UserRepository.REPOSITORY.getUserByName(name);
""",
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())