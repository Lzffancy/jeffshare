---
title: The Clean Architecture — 从 MVC 到分层架构的演进
date: 2026-08-12
tags:
  - 架构设计
  - Clean Architecture
  - MVC
  - 软件工程
draft: false
---

> 原文参考：[The Clean Architecture — Uncle Bob](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)

![Clean Architecture](/images/clean-arch-diagram.png)

## MVC（Model-View-Controller）

MVC 是一种常见的设计模式，主要用于构建用户界面。它将应用程序分为三个主要部分：

1. **Model（模型）**：表示应用程序的数据和业务逻辑。模型负责数据的获取、存储和处理。
2. **View（视图）**：负责显示数据并向用户呈现界面。视图通常是用户界面的一部分。
3. **Controller（控制器）**：处理用户输入并与模型和视图进行交互。控制器接收用户的输入，调用模型进行处理，然后更新视图。

## Clean Architecture

Clean Architecture 是一种更为广泛的架构设计理念，旨在创建**可维护、可扩展和可测试**的系统。它强调将系统分为多个层次，每一层都有明确的职责。主要层次包括：

1. **Entities（实体）**：业务规则和核心逻辑，通常是领域模型。
2. **Use Cases（用例）**：应用程序的业务逻辑，定义了系统的功能。
3. **Interface Adapters（接口适配器）**：将数据从外部格式转换为内部格式，通常包括控制器、视图模型等。
4. **Frameworks and Drivers（框架和驱动）**：外部工具和库，如数据库、Web 框架等。

## 主要区别

### 1. 关注点

- **MVC**：主要关注用户界面的构建和用户交互。它将应用程序的不同部分分开，以便于管理用户输入和界面更新。
- **Clean Architecture**：关注整个系统的结构和可维护性，强调业务逻辑和应用程序的核心功能。它不仅限于用户界面，还包括数据存储、外部服务等。

### 2. 层次结构

- **MVC**：通常是一个单层结构，虽然可以在模型中包含业务逻辑，但它并不强制分层。
- **Clean Architecture**：明确分层，每一层都有特定的职责，强调**依赖反转**和接口的使用。

### 3. 可测试性

- **MVC**：虽然可以进行单元测试，但由于模型、视图和控制器之间的紧密耦合，可能会导致测试变得复杂。
- **Clean Architecture**：通过分层和依赖反转，增强了可测试性。每一层可以独立测试，且高层不依赖于低层的具体实现。

### 4. 灵活性和扩展性

- **MVC**：在用户界面变化时，可能需要对控制器和视图进行较大修改。
- **Clean Architecture**：由于其分层结构，系统的不同部分可以独立演进，增加了灵活性和扩展性。

## 总结

虽然 Clean Architecture 和 MVC 都是用于构建软件系统的架构模式，但它们的关注点、结构和设计原则有所不同：

- **MVC** 更加专注于用户界面的构建和交互。
- **Clean Architecture** 提供了一种更为全面和灵活的方式来组织代码，适用于更复杂的应用程序。

## 实践：BackendApiProxy 的 Clean Architecture 落地

区别于传统 MVC 的架构，我们借鉴了 Clean Architecture 的设计思想，同时参考了 [trpc-go 的目录规范](https://go-kratos.dev/docs/intro/layout)，对业务代码进行了整理。

![目录结构设计](/images/clean-arch-dir-structure.png)

作为鉴权网关服务，BackendApiProxy 更适合使用 Clean Architecture 的思想，将功能单一拆分为：

- **service（服务代码层 / 协议层 / 服务入口）**：BackendApiProxy 的服务入口较为收敛，提供有限的 API，不单独作为目录，直接以 `service.go` 文件放在工程目录中与 `main.go` 同级。

- **logic（服务具体业务逻辑层）**：BackendApiProxy 的主要业务为转发 HTTP 请求为 TCP 请求到后台，所以 logic 层的 handler 功能主要为高效转发和颁发鉴权 ticket。

- **repository（外部依赖层 / 数据资源库）**：BackendApiProxy 中主要依赖外部配置文件（七彩石）作为配置接入，配置信息作为一种资源接入 repo 进行 CRUD 操作。

- **entity（服务内部共用的实体结构层）**：包括通用的报错结构体、通用的网络、日志、插件功能。

- **middleware（中间件层）**：BackendApiProxy 业务独有，利用 gin 框架的中间件开发能力，实现了主要的鉴权逻辑。鉴权作为请求到来的预处理行为，不应杂糅在业务中，所以单独作为一层。

最终形成如下代码目录：

![最终目录结构](/images/clean-arch-final-dir.png)

## 延伸阅读

- [The Clean Architecture — Uncle Bob](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Kratos 项目结构指南](https://go-kratos.dev/docs/intro/layout)
