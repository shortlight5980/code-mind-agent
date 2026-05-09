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