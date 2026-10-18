// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

contract Arithmetic {
    int256 public firstNumber;
    int256 public secondNumber;
    int256 public result;

    function add(int256 a, int256 b) external returns (int256) {
        firstNumber = a;
        secondNumber = b;
        result = a + b;
        return result;
    }

    function subtract(int256 a, int256 b) external returns (int256) {
        firstNumber = a;
        secondNumber = b;
        result = a - b;
        return result;
    }

    function multiply(int256 a, int256 b) external returns (int256) {
        firstNumber = a;
        secondNumber = b;
        result = a * b;
        return result;
    }

    function divide(int256 a, int256 b) external returns (int256) {
        require(b != 0, "Division by zero");
        firstNumber = a;
        secondNumber = b;
        result = a / b;
        return result;
    }
}
