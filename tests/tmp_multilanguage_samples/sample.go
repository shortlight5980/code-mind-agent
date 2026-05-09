package main

func greet(name string) string {
    return "hello " + name
}

func (s Service) Run() error {
    return nil
}