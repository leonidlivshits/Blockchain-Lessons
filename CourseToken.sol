// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {ERC20} from "@openzeppelin/contracts@5.4.0/token/ERC20/ERC20.sol";

contract CourseToken is ERC20 {
    constructor() ERC20("Course Token", "CRS") {
        _mint(msg.sender, 100 * 10 ** decimals());
    }
}
