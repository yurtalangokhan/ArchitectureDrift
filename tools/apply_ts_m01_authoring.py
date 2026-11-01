from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

WORKSPACE = (
    PROJECT_ROOT
    / "workspaces"
    / "authoring"
    / "teastore"
    / "TS-M01"
)

AUTH_USER_ACTIONS = (
    WORKSPACE
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


def read_preserving_newline(
    path: Path,
) -> tuple[str, str]:
    raw = path.read_bytes()

    newline = (
        "\r\n"
        if b"\r\n" in raw
        else "\n"
    )

    text = raw.decode(
        "utf-8-sig"
    )

    return (
        text.replace("\r\n", "\n"),
        newline,
    )


def write_preserving_newline(
    path: Path,
    content: str,
    newline: str,
) -> None:
    serialized = content.replace(
        "\n",
        newline,
    )

    path.write_bytes(
        serialized.encode("utf-8")
    )


def replace_once(
    content: str,
    old: str,
    new: str,
    *,
    name: str,
    already_applied_marker: str,
) -> str:
    if already_applied_marker in content:
        print(
            f"[SKIP] {name}: already applied"
        )
        return content

    count = content.count(
        old
    )

    if count != 1:
        raise RuntimeError(
            f"{name}: expected exactly one "
            f"replacement target, found {count}"
        )

    print(
        f"[APPLY] {name}"
    )

    return content.replace(
        old,
        new,
        1,
    )


def main() -> int:
    if not AUTH_USER_ACTIONS.is_file():
        raise FileNotFoundError(
            "AuthUserActionsRest.java not found: "
            f"{AUTH_USER_ACTIONS}"
        )

    content, newline = (
        read_preserving_newline(
            AUTH_USER_ACTIONS
        )
    )

    content = replace_once(
        content,
        """import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;""",
        """import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.URL;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;""",
        name="TS-M01 HTTP imports",
        already_applied_marker=(
            "import java.net.HttpURLConnection;"
        ),
    )

    content = replace_once(
        content,
        """public class AuthUserActionsRest {

  /**
   * Persists order in database.""",
        """public class AuthUserActionsRest {

  private static final String TS_M01_RECOMMENDER_URL =
      "http://recommender:8080/"
      + "tools.descartes.teastore.recommender/"
      + "rest/train/isready";

  private static void invokeTSM01Recommender() {
    HttpURLConnection connection = null;

    try {
      URL url = new URL(
          TS_M01_RECOMMENDER_URL);

      connection = (HttpURLConnection)
          url.openConnection();

      connection.setRequestMethod("GET");
      connection.setConnectTimeout(1000);
      connection.setReadTimeout(1000);

      connection.getResponseCode();
    } catch (IOException ignored) {
      // The controlled mutation must not alter
      // the Authentication business outcome.
    } finally {
      if (connection != null) {
        connection.disconnect();
      }
    }
  }

  /**
   * Persists order in database.""",
        name="TS-M01 recommender client",
        already_applied_marker=(
            "TS_M01_RECOMMENDER_URL"
        ),
    )

    content = replace_once(
        content,
        """  public Response login(SessionBlob blob, @QueryParam("name") String name,
      @QueryParam("password") String password) {
    User user;""",
        """  public Response login(SessionBlob blob, @QueryParam("name") String name,
      @QueryParam("password") String password) {
    invokeTSM01Recommender();

    User user;""",
        name="TS-M01 login invocation",
        already_applied_marker=(
            "    invokeTSM01Recommender();"
        ),
    )

    write_preserving_newline(
        AUTH_USER_ACTIONS,
        content,
        newline,
    )

    print()
    print(
        f"Updated: {AUTH_USER_ACTIONS}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )