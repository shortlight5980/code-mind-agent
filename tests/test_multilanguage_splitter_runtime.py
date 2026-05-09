import unittest

from tests.test_index_repo_split import index_repo


class RaisingFallback(index_repo.CodeSplitter):
    def split(self, content: str, max_class_length: int = 3000) -> list[str]:
        raise AssertionError("tree-sitter splitter unexpectedly used fallback")


class MultilanguageTreeSitterRuntimeTests(unittest.TestCase):
    def _split_without_fallback(
        self,
        language_name: str,
        content: str,
        max_class_length: int = 3000,
    ) -> list[str]:
        splitter = index_repo.TreeSitterCodeSplitter(language_name, RaisingFallback())
        return splitter.split(content, max_class_length=max_class_length)

    def test_tsx_chunks_exported_component_and_arrow_function(self):
        content = """
import React from "react";

interface Props {
  name: string;
}

export function Header() {
  return <h1>Hi</h1>;
}

const Hello: React.FC<Props> = ({ name }) => {
  return <div>Hello, {name}</div>;
};
""".strip()

        blocks = self._split_without_fallback("tsx", content)

        self.assertEqual(3, len(blocks))
        self.assertTrue(blocks[0].startswith('import React from "react";'))
        self.assertIn("interface Props", blocks[0])
        self.assertTrue(blocks[1].startswith("export function Header"))
        self.assertTrue(blocks[2].startswith("const Hello"))

    def test_java_chunks_class_declaration(self):
        content = """
package demo;

public class Service {
    public String greet(String name) {
        return "hello " + name;
    }
}
""".strip()

        blocks = self._split_without_fallback("java", content)

        self.assertEqual(2, len(blocks))
        self.assertEqual("package demo;", blocks[0])
        self.assertTrue(blocks[1].startswith("public class Service"))
        self.assertIn("public String greet", blocks[1])

    def test_rust_chunks_struct_impl_and_function(self):
        content = """
struct Service {
    name: String,
}

impl Service {
    fn run(&self) -> bool {
        true
    }
}

fn helper() -> i32 {
    1
}
""".strip()

        blocks = self._split_without_fallback("rust", content)

        self.assertEqual(3, len(blocks))
        self.assertTrue(blocks[0].startswith("struct Service"))
        self.assertTrue(blocks[1].startswith("impl Service"))
        self.assertTrue(blocks[2].startswith("fn helper"))

    def test_c_and_cpp_chunks_functions_and_classes(self):
        c_blocks = self._split_without_fallback(
            "c",
            """
int add(int a, int b) {
    return a + b;
}
""".strip(),
        )
        cpp_blocks = self._split_without_fallback(
            "cpp",
            """
class Greeter {
public:
    void run();
};

int add(int a, int b) {
    return a + b;
}
""".strip(),
        )

        self.assertEqual(1, len(c_blocks))
        self.assertTrue(c_blocks[0].startswith("int add"))
        self.assertEqual(2, len(cpp_blocks))
        self.assertTrue(cpp_blocks[0].startswith("class Greeter"))
        self.assertTrue(cpp_blocks[1].startswith("int add"))

    def test_javascript_keeps_small_class_whole_instead_of_splitting_methods(self):
        content = """
class Service {
  start() {
    return true;
  }

  stop() {
    return false;
  }
}

function helper() {
  return 1;
}
""".strip()

        blocks = self._split_without_fallback("javascript", content)

        self.assertEqual(2, len(blocks))
        self.assertTrue(blocks[0].startswith("class Service"))
        self.assertIn("start()", blocks[0])
        self.assertIn("stop()", blocks[0])
        self.assertTrue(blocks[1].startswith("function helper"))

    def test_javascript_splits_large_class_by_methods(self):
        content = """
class LargeService {
  start() {
    return true;
  }

  stop() {
    return false;
  }
}
""".strip()

        blocks = self._split_without_fallback("javascript", content, max_class_length=10)

        self.assertEqual(2, len(blocks))
        self.assertTrue(blocks[0].startswith("start()"))
        self.assertTrue(blocks[1].startswith("stop()"))

    def test_javascript_preserves_top_level_gap_and_tail_fragments(self):
        content = """
import React from "react";
export const config = { enabled: true };

class Service {
  start() {
    return true;
  }
}

export type Mode = "dark" | "light";

function helper() {
  return 1;
}

const tailValue = helper();
console.log(tailValue);
""".strip()

        blocks = self._split_without_fallback("javascript", content)

        self.assertEqual(5, len(blocks))
        self.assertTrue(blocks[0].startswith('import React from "react";'))
        self.assertIn("export const config", blocks[0])
        self.assertTrue(blocks[1].startswith("class Service"))
        self.assertEqual('export type Mode = "dark" | "light";', blocks[2])
        self.assertTrue(blocks[3].startswith("function helper"))
        self.assertTrue(blocks[4].startswith("const tailValue"))

    def test_large_class_preserves_surrounding_fragments(self):
        content = """
const before = 1;

class LargeService {
  start() {
    return true;
  }

  stop() {
    return false;
  }
}

const after = 2;
""".strip()

        blocks = self._split_without_fallback("javascript", content, max_class_length=10)

        self.assertEqual(4, len(blocks))
        self.assertEqual("const before = 1;", blocks[0])
        self.assertTrue(blocks[1].startswith("start()"))
        self.assertTrue(blocks[2].startswith("stop()"))
        self.assertEqual("const after = 2;", blocks[3])


if __name__ == "__main__":
    unittest.main()
