from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.test_index_repo_split import index_repo


SAMPLES = {
    "sample.py": """
import os

def greet(name):
    return f"hello {name}"

class Service:
    def run(self):
        return os.getcwd()
""".strip(),
    "sample.jsx": """
import React from "react";

class ViewModel {
  start() {
    return true;
  }

  stop() {
    return false;
  }
}

export function Header() {
  return <h1>Header</h1>;
}

const Hello = ({ name }) => {
  return <div>Hello, {name}</div>;
};
""".strip(),
    "sample.tsx": """
import React from "react";

interface Props {
  name: string;
}

const Hello: React.FC<Props> = ({ name }) => {
  return <div>Hello, {name}</div>;
};
""".strip(),
    "sample.go": """
package main

func greet(name string) string {
    return "hello " + name
}

func (s Service) Run() error {
    return nil
}
""".strip(),
    "sample.rs": """
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
""".strip(),
    "sample.java": """
package demo;

public class Service {
    public String greet(String name) {
        return "hello " + name;
    }
}
""".strip(),
    "sample.c": """
int add(int a, int b) {
    return a + b;
}
""".strip(),
    "sample.cpp": """
class Greeter {
public:
    void run();
};

int add(int a, int b) {
    return a + b;
}
""".strip(),
}


def main():
    sample_dir = Path(__file__).resolve().parent / "tmp_multilanguage_samples"
    sample_dir.mkdir(exist_ok=True)

    for filename, content in SAMPLES.items():
        path = sample_dir / filename
        path.write_text(content, encoding="utf-8")

        splitter = index_repo.get_code_splitter(path.suffix)
        blocks = splitter.split(content, max_class_length=3000)

        print(f"=== {filename} | {type(splitter).__name__} | {len(blocks)} chunks ===")
        for idx, block in enumerate(blocks, 1):
            first_line = block.splitlines()[0] if block else ""
            print(f"{idx}. {first_line}")

    large_class = """
class LargeService {
  start() {
    return true;
  }

  stop() {
    return false;
  }
}
""".strip()
    splitter = index_repo.get_code_splitter(".js")
    blocks = splitter.split(large_class, max_class_length=10)
    print(f"=== large_class.js | {type(splitter).__name__} | {len(blocks)} chunks ===")
    for idx, block in enumerate(blocks, 1):
        first_line = block.splitlines()[0] if block else ""
        print(f"{idx}. {first_line}")


if __name__ == "__main__":
    main()
