package com.test.login;

import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class HomeAssetContractTest {

    private static final List<String> SCRIPT_NAMES = List.of(
            "core",
            "chat",
            "memory",
            "knowledge",
            "task",
            "observability",
            "app"
    );

    @Test
    void shouldKeepOnlyTheThymeleafBootstrapInlineAndLoadDeferredAssetsInOrder() throws IOException {
        String template = readResource("templates/home.html");

        assertThat(template)
                .contains("<meta name=\"_csrf\" th:content=\"${_csrf.token}\">")
                .contains("<meta name=\"_csrf_header\" th:content=\"${_csrf.headerName}\">")
                .contains("<script th:inline=\"javascript\">")
                .contains("const currentUserId = /*[[${user.id}]]*/ 0;")
                .contains("const currentUsername = /*[[${user.username}]]*/ \"\";")
                .contains("th:href=\"@{/css/home.css}\"")
                .contains("th:src=\"@{/images/icon.svg}\"")
                .doesNotContain("icon.jpg")
                .doesNotContain("<style>");
        assertThat(template.split("<script", -1).length - 1)
                .as("one inline bootstrap plus seven external scripts")
                .isEqualTo(SCRIPT_NAMES.size() + 1);

        int previousPosition = template.indexOf("</script>", template.indexOf("th:inline=\"javascript\""));
        for (String name : SCRIPT_NAMES) {
            String scriptTag = "<script src=\"/js/home/" + name + ".js\" "
                    + "th:src=\"@{/js/home/" + name + ".js}\" defer></script>";
            int position = template.indexOf(scriptTag);
            assertThat(position)
                    .as("%s.js must load after the bootstrap and the preceding asset", name)
                    .isGreaterThan(previousPosition);
            previousPosition = position;
        }
    }

    @Test
    void shouldPackageEveryHomeAssetAndKeepInitializationLast() throws IOException {
        assertThat(readResource("static/css/home.css"))
                .contains("#main-interface")
                .contains(".sidebar")
                .contains("@media (max-width: 768px)");
        assertThat(readResource("static/images/icon.svg"))
                .contains("<title id=\"myai-icon-title\">MyAI</title>")
                .contains("aria-labelledby=\"myai-icon-title\"");

        String allScripts = "";
        for (String name : SCRIPT_NAMES) {
            String script = readResource("static/js/home/" + name + ".js");
            assertThat(script).as(name + ".js").isNotBlank();
            allScripts += script;
        }

        assertThat(allScripts)
                .contains("function csrfHeaders()")
                .contains("async function sendChatMessage()")
                .contains("async function writeMemory()")
                .contains("async function uploadKnowledge()")
                .contains("async function executeTask()")
                .contains("async function loadObservabilityWorkbench()");
        assertThat(readResource("static/js/home/app.js"))
                .contains("document.addEventListener(\"DOMContentLoaded\"")
                .contains("loadConversations();");
    }

    private String readResource(String path) throws IOException {
        ClassLoader classLoader = Thread.currentThread().getContextClassLoader();
        try (InputStream input = classLoader.getResourceAsStream(path)) {
            assertThat(input).as("classpath resource %s", path).isNotNull();
            return new String(input.readAllBytes(), StandardCharsets.UTF_8);
        }
    }
}
