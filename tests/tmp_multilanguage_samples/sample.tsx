import React from "react";

interface Props {
  name: string;
}

const Hello: React.FC<Props> = ({ name }) => {
  return <div>Hello, {name}</div>;
};