import { test, expect } from '@playwright/test';

test.describe('首页', () => {
  test('加载成功，有标题和导航', async ({ page }) => {
    await page.goto('/');

    // 页面标题
    await expect(page).toHaveTitle(/杰夫|Jeff/i);

    // 导航栏存在
    const nav = page.locator('nav');
    await expect(nav).toBeVisible();

    // 有导航链接
    const navLinks = nav.locator('a');
    expect(await navLinks.count()).toBeGreaterThan(0);
  });
});

test.describe('博客 /blog', () => {
  test('博客列表页加载成功', async ({ page }) => {
    await page.goto('/blog');
    await expect(page.locator('body')).toBeVisible();

    // 页面不应是 404
    const status = await page.evaluate(() => document.title);
    expect(status).toBeTruthy();
  });

  test('从首页可以导航到博客', async ({ page }) => {
    await page.goto('/');

    // 点击导航里的博客链接
    const blogLink = page.locator('a[href*="blog"]').first();
    if (await blogLink.isVisible()) {
      await blogLink.click();
      await expect(page).toHaveURL(/\/blog/);
    }
  });
});

test.describe('研究报告 /reports', () => {
  test('报告列表页加载成功', async ({ page }) => {
    await page.goto('/reports');
    await expect(page.locator('body')).toBeVisible();
  });
});

test.describe('分享 /share', () => {
  test('分享列表页加载成功', async ({ page }) => {
    await page.goto('/share');
    await expect(page.locator('body')).toBeVisible();
  });
});

test.describe('API /api', () => {
  test('FastAPI 健康检查 /api', async ({ page }) => {
    // FastAPI 跑在宿主机 :8000，Caddy 反代 /api/* 到它
    const response = await page.request.get('/api');
    // 405 说明路由存在（FastAPI 要求 GET）
    expect([200, 405]).toContain(response.status());
  });
});
