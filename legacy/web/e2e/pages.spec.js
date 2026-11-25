import {expect,test} from '@playwright/test';

test('Pages landing opens the Neon-backed wardrobe and demo',async({page},testInfo)=>{
  const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.goto('./');
  await expect(page.getByRole('heading',{level:1})).toContainText('Dress for the');
  const hero=page.locator('.hero-figure img');
  await expect(hero).toBeVisible();
  await expect.poll(()=>hero.evaluate(image=>image.naturalWidth)).toBeGreaterThan(0);
  await page.getByRole('link',{name:'Open my wardrobe',exact:true}).first().click();
  await expect(page.getByRole('heading',{name:'Fitting room',exact:true})).toBeVisible();
  await expect(page.getByText('Manual weather needed',{exact:true})).not.toBeVisible();
  await expect(page.locator('.weather').first()).toContainText(/°C/);
  await page.getByLabel('Time (WIB)').fill(new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Jakarta',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date()));
  await page.getByRole('button',{name:'Find outfits'}).click();
  await expect(page.getByRole('heading',{name:'Best match',exact:true})).toBeVisible({timeout:15000});
  await page.getByRole('link',{name:'My wardrobe',exact:true}).click();
  await expect(page.getByRole('heading',{name:'My wardrobe',exact:true})).toBeVisible();
  await expect(page.getByText('Pink oxford shirt',{exact:true}).first()).toBeVisible();
  await page.getByRole('link',{name:'Demo',exact:true}).click();
  await expect(page.getByText('Database neon',{exact:true})).toBeVisible();
  await expect(page.getByLabel('Product').locator('option')).toHaveCount(5);
  await page.screenshot({path:testInfo.outputPath('desktop.png'),fullPage:true});
  expect(errors).toEqual([]);
});

test('mobile landing and wardrobe remain within the viewport',async({page},testInfo)=>{
  await page.setViewportSize({width:390,height:844});
  await page.goto('./');
  await expect(page.getByRole('heading',{level:1})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.getByRole('link',{name:'Open my wardrobe',exact:true}).first().click();
  await expect(page.getByRole('heading',{name:'Fitting room',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Find outfits'})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.screenshot({path:testInfo.outputPath('mobile.png'),fullPage:true});
});

test('QR link and pasted tag both register clothing',async({page,request})=>{
  const base=process.env.TEST_API_URL;
  test.skip(!base?.includes('br-noisy-frog-bivp6wyg-'),'Registration mutations use only the dedicated test branch');
  const headers={'X-API-Key':'deployment-test-key'};
  const products=await (await request.get(base+'/api/v1/admin/products',{headers})).json();
  const issue=async()=>{
    const r=await request.post(base+'/api/v1/admin/codes',{headers,data:{gtin:products[0].gtin}});
    expect(r.status()).toBe(201);return (await r.json())[0];
  };
  const first=await issue();
  await page.goto(`${base}/01/${first.gtin}/21/${first.serial}`);
  await expect(page.locator('#result')).toContainText('added to your wardrobe');
  const used=await request.post(base+'/api/v1/garments/activate',{headers,data:{code:first.activation_code}});
  expect(used.status()).toBe(400);
  const second=await issue();
  await page.goto('./app/#/register');
  await page.getByLabel('Or paste the tag link').fill(`${base}/01/${second.gtin}/21/${second.serial}`);
  await page.getByRole('button',{name:'Add garment from QR'}).click();
  await expect(page.getByRole('link',{name:'See my wardrobe'})).toBeVisible();
  const wardrobe=await (await request.get(base+'/api/v1/wardrobe')).json();
  expect(wardrobe.filter(g=>g.serial===second.serial)).toHaveLength(1);
});
