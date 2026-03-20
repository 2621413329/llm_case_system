CREATE DATABASE IF NOT EXISTS llm_case_system;

USE llm_case_system;

-- 创建系统表
CREATE TABLE IF NOT EXISTS system_tables (
    id INT AUTO_INCREMENT PRIMARY KEY,
    system_name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建菜单结构表
CREATE TABLE IF NOT EXISTS menu_structures (
    id INT AUTO_INCREMENT PRIMARY KEY,
    system_id INT,
    level INT,
    name VARCHAR(255) NOT NULL,
    parent_id INT,
    FOREIGN KEY (system_id) REFERENCES system_tables(id)
);

-- 创建截图表
CREATE TABLE IF NOT EXISTS screenshots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    system_id INT,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    menu_structure TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (system_id) REFERENCES system_tables(id)
);

-- 创建历史记录表
CREATE TABLE IF NOT EXISTS history_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    screenshot_id INT,
    operation_type VARCHAR(50) NOT NULL,
    operation_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (screenshot_id) REFERENCES screenshots(id)
);

-- 插入测试数据
INSERT INTO system_tables (system_name, description) VALUES ('测试系统', '用于测试的系统');

INSERT INTO menu_structures (system_id, level, name, parent_id) VALUES 
(1, 1, '一级菜单', NULL),
(1, 2, '二级菜单', 1),
(1, 3, '三级菜单', 2);

INSERT INTO screenshots (system_id, file_name, file_path, menu_structure) VALUES 
(1, '测试系统_一级菜单_二级菜单_三级菜单.png', 'uploads/测试系统_一级菜单_二级菜单_三级菜单.png', '{"level1": "一级菜单", "level2": "二级菜单", "level3": "三级菜单"}');

INSERT INTO history_records (screenshot_id, operation_type) VALUES (1, '上传');
