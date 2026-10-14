/* Standalone design preview only. No storage, network or real authentication. */
window.CIRCLELOGIC_PREVIEW=true;
window.previewState={stage:'anonymous',example:false};
(function(){
 const providerNames={agentbox:'Agentbox',rea:'REA Ignite',rpdata:'RP Data',proping:'Proping',microsoft:'Calendar'};
 const metricDefs=[['contacts','Total contacts','agentbox',8432,12,'users'],['enquiries','New enquiries','agentbox',284,18,'message'],['buyers','High-intent buyers','rea',56,22,'activity'],['listings','Active listings','agentbox',38,-5,'home'],['properties','Property records','rpdata',126,14,'chart']];
 const user={id:'preview-user',username:'testing123',name:'Testing account',email:'testing123@preview.invalid',agency:'CircleLogic Testing',workspace_id:'design-preview',role:'owner',mfa_enabled:true};
 function dashboard(){
  const sample=window.previewState.example;
  const base={rows:[],total:null,synced_at:null,mode:sample?'example':'unavailable'};
  const metrics=metricDefs.map(([id,title,provider,value,delta,icon])=>({id,title,provider,value:sample?value:null,delta:sample?delta:null,icon,mode:sample?'example':'unavailable',description:id==='buyers'?'Illustrative score only. A separately approved buyer-score feed and agreed criteria are required.':'Design example of a '+providerNames[provider]+' metric. Not an imported business record.',synced_at:null}));
  const buyer_activity={...base,provider:'rea',rows:sample?[['12 Oceanview Road','Bondi',92],['28 Park Street','Coogee',76],['5 Hillcrest Avenue','Rose Bay',54],['14 Beach Road','Manly',38],['3 Kent Street','Sydney',22]].map(([title,suburb,score])=>({title,suburb,score})):[],total:sample?5:null};
  const market_activity={...base,provider:'proping',rows:sample?[['New listings',42],['Price changes',18],['Withdrawn',6],['Sold',27]].map(([title,count])=>({title,count})):[],total:sample?93:null};
  const now=Date.now();
  const events=[['Property inspection','12 Oceanview Rd',1,9],['Vendor meeting','28 Park St',2,10],['Team planning','Office',3,14],['Property appraisal','5 Hillcrest Ave',9,11]].map(([title,location,days,hour])=>{
   const d=new Date(now+days*86400000);d.setUTCHours(hour-10,0,0,0);if(d.getTime()<now)d.setUTCDate(d.getUTCDate()+1);
   return {title,location,start:d.toISOString(),end:new Date(d.getTime()+3600000).toISOString(),timezone:'UTC',status:'Scheduled'};
  });
  return {mode:sample?'example':'empty',metrics,buyer_activity,market_activity,calendar:{...base,provider:'microsoft',rows:sample?events:[],total:sample?4:null},generated_at:now/1000,workspace_id:'design-preview'};
 }
 window.previewApi=async function(path,method='GET',body={}){
  const s=window.previewState;
  if(path==='/auth/session')return {authenticated:s.stage==='full',stage:s.stage,csrf:'preview-only',user:s.stage==='full'?user:null,mfa_recent:true,environment:'preview'};
  if(path==='/auth/login'&&method==='POST'){
   if((body.username||'').trim().toLowerCase()!=='testing123'||body.password!=='testing12345')throw Error('Use the local preview credentials shown below the form.');
   s.stage='enrol';return {stage:'enrol',csrf:'preview-only'};
  }
  if(path==='/auth/mfa'&&method==='POST'){
   if(s.stage!=='enrol'||body.code!=='123456')throw Error('For this simulated preview, enter 123456. The full application uses real authenticator codes.');
   s.stage='full';return {csrf:'preview-only',ok:true,recovery_codes:[]};
  }
  if(path==='/auth/logout'){s.stage='anonymous';s.example=false;return {ok:true};}
  if(s.stage!=='full')throw Error('Sign into the design preview first.');
  if(path==='/brain/dashboard')return dashboard();
  if(path==='/brain/connections')return {connections:window.PREVIEW_CONNECTIONS.map(c=>({...c,status:s.example?'example':'not_connected',has_credentials:s.example&&c.implemented,last_success:null,callback:c.id==='microsoft'?'https://your-approved-host.example/api/oauth/microsoft/callback':null}))};

  if(path==='/integrations')return {integrations:window.PREVIEW_CONNECTIONS.map(c=>({...c,status:s.example?'example':'not_connected',has_credentials:s.example&&c.implemented,last_success:null,callback:c.id==='microsoft'?'https://your-approved-host.example/api/oauth/microsoft/callback':null}))};
  throw Error('This operation requires the backend application. Real credentials are never accepted by the preview.');
 };
})();
