import {expect,test} from '@playwright/test';

test('landing timeline changes conditions without requesting recommendations',async({page})=>{
  const calls=[];
  page.on('request',request=>{if(request.url().includes('/outfits/recommend'))calls.push(request.url());});
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'Dress for the weather you’ll actually get.'})).toBeVisible();
  const slider=page.getByRole('slider',{name:'Example forecast'});
  await slider.focus();
  await slider.press('Home');
  await slider.press('ArrowRight');
  await expect(page.getByText('Hujan Ringan',{exact:true})).toBeVisible();
  expect(calls).toHaveLength(0);
});
test('offline demo supports live, cached, manual and single-use activation',async({page,request})=>{
  const health=await request.get('/api/v1/health');
  expect(health.ok(),'Start the offline demo server on port 8000 before running this test').toBeTruthy();
  const config={headers:{'X-API-Key':process.env.VITE_API_KEY||'demo-key'}};
  const resetFault=()=>request.post('/api/v1/admin/fault',{...config,data:{mode:'none'}});
  try{
    await resetFault();
    await request.post('/api/v1/admin/weather/clear-cache',config);
    await page.goto('/app/#/');
    await page.getByLabel('Time (WIB)').fill(process.env.DEMO_TEST_TIME||'14:00');
    await page.getByRole('button',{name:'Find outfits'}).click();
    await expect(page.getByText('Live forecast',{exact:true})).toBeVisible();
    await page.getByRole('button',{name:'Find outfits'}).click();
    await expect(page.getByText('Cached forecast',{exact:true})).toBeVisible();
    await page.getByRole('link',{name:'Demo',exact:true}).click();
    await page.getByLabel('Simulate a BMKG fault').selectOption('timeout');
    await page.getByRole('button',{name:'Apply fault'}).click();
    await expect(page.getByText('Fault timeout')).toBeVisible();
    await page.getByRole('link',{name:'Fitting room',exact:true}).click();
    await page.getByRole('button',{name:'Find outfits'}).click();
    await expect(page.getByText('Cached forecast',{exact:true})).toBeVisible();
    await page.getByRole('link',{name:'Demo',exact:true}).click();
    await page.getByRole('button',{name:'Clear weather cache'}).click();
    await expect(page.getByRole('status')).toContainText('Weather cache cleared');
    await page.getByRole('link',{name:'Fitting room',exact:true}).click();
    await page.getByRole('button',{name:'Find outfits'}).click();
    await page.getByRole('radio',{name:'Rainy'}).check();
    await page.getByRole('radio',{name:'Normal'}).check();
    await page.getByRole('button',{name:'Use these conditions'}).click();
    await expect(page.getByText('Manual weather',{exact:true})).toBeVisible();
    await page.getByRole('link',{name:'Demo',exact:true}).click();
    await page.getByLabel('Product').selectOption({index:1});
    await page.getByRole('button',{name:'Issue code'}).click();
    const code=await page.locator('.notice strong').innerText();
    await page.getByRole('link',{name:'Register',exact:true}).click();
    await page.getByLabel('Private activation code').fill(code);
    await page.getByRole('button',{name:'Activate garment'}).click();
    await expect(page.getByRole('link',{name:'See my wardrobe'})).toBeVisible();
    await page.getByLabel('Private activation code').fill(code);
    await page.getByRole('button',{name:'Activate garment'}).click();
    await expect(page.getByRole('alert')).toContainText(/invalid code/i);
  } finally { await resetFault(); }
});
