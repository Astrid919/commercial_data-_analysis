# Official CMS extraction. Run from the project directory.
try(Sys.setlocale('LC_ALL','English_United States.utf8'),silent=TRUE)
library(data.table); library(jsonlite); library(curl)
options(timeout=600); setDTthreads(4)
for(d in c('data/raw','data/processed','logs')) dir.create(d,recursive=TRUE,showWarnings=FALSE)
catalog <- fromJSON('data/raw/cms_catalog.json',simplifyVector=FALSE)$dataset
titles <- c(B='Medicare Physician & Other Practitioners - by Provider',D='Medicare Part D Prescribers - by Provider and Drug',G='Medicare Part D Prescribers - by Geography and Drug')
manifest <- rbindlist(lapply(names(titles),function(p) {
 ds <- Filter(function(x) identical(x$title,titles[[p]]),catalog)[[1]]
 rbindlist(lapply(ds$distribution,function(d) data.table(dataset=p,year=as.integer(substr(d$temporal,1,4)),url=if(is.null(d$downloadURL)) NA_character_ else d$downloadURL,api=if(is.null(d$accessURL)) NA_character_ else d$accessURL)),fill=TRUE)
}))[year %in% 2019:2024]
fwrite(manifest,'data/raw/source_manifest.csv')
api_for <- function(p,y) tail(manifest[dataset==p & year==y & !is.na(api)]$api,1)
encode_in_filter <- function(key,path,values) {
 paste0('filter%5B',key,'%5D%5Bcondition%5D%5Bpath%5D=',path,
        '&filter%5B',key,'%5D%5Bcondition%5D%5Boperator%5D=IN&',
        paste0('filter%5B',key,'%5D%5Bcondition%5D%5Bvalue%5D%5B%5D=',
               vapply(values,curl::curl_escape,character(1)),collapse='&'))
}
offset_text <- function(x) format(as.integer(x),scientific=FALSE,trim=TRUE)
download_batch <- function(urls,files) {
 todo <- !file.exists(files) | file.size(files)==0
 if(!any(todo)) return(invisible(NULL))
 if(.Platform$OS.type=='windows') {
  # The CMS edge server accepts Windows HTTP requests more reliably on this host.
  # R remains the orchestration and analysis language; this helper only transfers bytes.
  tasksfile <- tempfile(pattern='download_tasks_',tmpdir='logs',fileext='.csv')
  fwrite(data.table(url=urls[todo],file=files[todo]),tasksfile)
  pwsh <- Sys.which('pwsh')
  if(!nzchar(pwsh)) pwsh <- Sys.which('powershell')
  if(!nzchar(pwsh)) stop('Neither pwsh nor Windows PowerShell is available')
  system2(pwsh,c('-NoProfile','-File','R/download_windows.ps1','-TaskFile',tasksfile))
  stopifnot(all(file.exists(files)),all(file.size(files)>0))
  return(invisible(NULL))
 }
 for(attempt in 1:4) {
  tmp <- paste0(files[todo],'.part')
  z <- curl::multi_download(urls[todo],tmp,progress=FALSE,timeout=600,connecttimeout=60)
  ok <- z$success & z$status_code==200
  if(any(!ok)) print(z[!ok,c('url','status_code','error')])
  if(any(ok)) file.rename(tmp[ok],files[todo][ok])
  cat(format(Sys.time()),'downloaded',sum(ok),'/',sum(todo),'\n'); flush.console()
  todo <- !file.exists(files) | file.size(files)==0
  if(!any(todo)) return(invisible(z))
 }
 stop('Failed downloads: ',paste(files[todo],collapse=', '))
}
args <- commandArgs(trailingOnly=TRUE)
mode <- if(length(args)) args[1] else 'catalogue'
if(mode=='catalogue') {
 tasks <- CJ(year=2019:2024,offset=c(0,5000,10000))
 tasks[,url:=mapply(function(y,o) paste0(api_for('G',y),'?filter[Prscrbr_Geo_Lvl]=National&size=5000&offset=',o),year,offset)]
 tasks[,file:=sprintf('data/raw/national_%d_%d.json',year,offset)]
 download_batch(tasks$url,tasks$file)
 g <- rbindlist(lapply(seq_len(nrow(tasks)),function(i){x<-as.data.table(fromJSON(tasks$file[i]));if(nrow(x))x[,year:=tasks$year[i]];x}),fill=TRUE)
 stopifnot(!any(g[, .N,by=.(year,Brnd_Name,Gnrc_Name)]$N>1))
 fwrite(g,'data/raw/national_drug_catalogue.csv')
 cat('national rows',nrow(g),'\n')
}
if(mode %in% c('partb','partb_history')) {
 tasks<-manifest[dataset=='B' & !is.na(url)]
 if(mode=='partb_history') tasks<-tasks[year<2024]
 tasks[,file:=sprintf('data/raw/partb_%d.csv',year)]
 download_batch(tasks$url,tasks$file)
}
if(grepl('^partb_api(_[0-9]{4})?$',mode)) {
 selected_years<-if(grepl('_[0-9]{4}$',mode)) as.integer(sub('^partb_api_','',mode)) else 2019:2024
 specialties<-c('Pulmonary Disease','Internal Medicine','Family Practice','Nurse Practitioner','Physician Assistant')
 filt<-encode_in_filter('specialty','Rndrng_Prvdr_Type',specialties)
 st<-data.table(year=selected_years)
 st[,url:=vapply(year,function(y) paste0(api_for('B',y),'/stats?',filt),character(1))]
 st[,file:=sprintf('data/raw/partb_targeted_stats_%d.json',year)]
 download_batch(st$url,st$file)
 st[,expected:=vapply(file,function(f) fromJSON(f)$found_rows,numeric(1))]
 print(st[,.(year,expected)])
 cols<-c('Rndrng_NPI','Rndrng_Prvdr_Type','Rndrng_Prvdr_State_Abrvtn','Rndrng_Prvdr_Zip5',
         'Rndrng_Prvdr_RUCA','Rndrng_Prvdr_Ent_Cd','Tot_Benes','Bene_Avg_Age','Bene_Dual_Cnt',
         'Bene_Avg_Risk_Scre','Bene_CC_PH_COPD_V2_Pct','Bene_CC_PH_Asthma_V2_Pct')
 tasks<-rbindlist(lapply(seq_len(nrow(st)),function(i) data.table(year=st$year[i],offset=seq(0,st$expected[i]-1,by=5000))))
 tasks[,url:=mapply(function(y,o) paste0(api_for('B',y),'?',filt,'&column=',paste(cols,collapse=','),'&size=5000&offset=',offset_text(o),'&sort=Rndrng_NPI'),year,offset)]
 # Older task manifests formatted exact 100k offsets in scientific notation
 # (for example 1e+05), which the CMS API interpreted incorrectly. Boundary
 # pages use a versioned filename so a corrected rerun never reuses those files.
 tasks[,file:=fifelse(offset>0 & offset%%100000==0,
                      sprintf('data/raw/partb_targeted_%d_fixed_%07d.json',year,offset),
                      sprintf('data/raw/partb_targeted_%d_%07d.json',year,offset))]
 fwrite(tasks,'data/raw/partb_targeted_download_tasks.csv')
 download_batch(tasks$url,tasks$file)
 for(y in selected_years) {
  rows<-tasks[year==y]
  dat<-rbindlist(lapply(rows$file,function(f) as.data.table(fromJSON(f))),fill=TRUE)
  stopifnot(nrow(dat)==st[year==y,expected],uniqueN(dat$Rndrng_NPI)==nrow(dat))
  fwrite(dat,sprintf('data/raw/partb_%d.csv',y))
  cat('Verified targeted Part B',y,nrow(dat),'rows\n')
 }
}
if(grepl('^partd(_[0-9]{4})?$',mode)) {
 selected_years<-if(grepl('_[0-9]{4}$',mode)) as.integer(sub('^partd_','',mode)) else 2019:2024
 mapping<-fread('data/processed/drug_mapping.csv')
 brands<-sort(unique(mapping$Brnd_Name))
 specialties<-c('Pulmonary Disease','Internal Medicine','Family Practice','Nurse Practitioner','Physician Assistant')
 filt<-paste(encode_in_filter('drug','Brnd_Name',brands),
             encode_in_filter('specialty','Prscrbr_Type',specialties),sep='&')
 st<-data.table(year=selected_years)
 st[,url:=vapply(year,function(y) paste0(api_for('D',y),'/stats?',filt),character(1))]
 st[,file:=sprintf('data/raw/partd_targeted_stats_%d.json',year)]
 download_batch(st$url,st$file)
 st[,expected:=vapply(file,function(f) fromJSON(f)$found_rows,numeric(1))]
 print(st[,.(year,expected)])
 cols<-c('Prscrbr_NPI','Prscrbr_Last_Org_Name','Prscrbr_First_Name','Prscrbr_City','Prscrbr_State_Abrvtn','Prscrbr_Type','Brnd_Name','Gnrc_Name','Tot_Clms','Tot_30day_Fills','Tot_Day_Suply','Tot_Drug_Cst','Tot_Benes')
 tasks<-rbindlist(lapply(seq_len(nrow(st)),function(i) data.table(year=st$year[i],offset=seq(0,st$expected[i]-1,by=5000))))
 tasks[,url:=mapply(function(y,o) paste0(api_for('D',y),'?',filt,'&column=',paste(cols,collapse=','),'&size=5000&offset=',offset_text(o),'&sort=Prscrbr_NPI,Brnd_Name,Gnrc_Name'),year,offset)]
 tasks[,file:=fifelse(offset>0 & offset%%100000==0,
                      sprintf('data/raw/partd_targeted_%d_fixed_%07d.json',year,offset),
                      sprintf('data/raw/partd_targeted_%d_%07d.json',year,offset))]
 fwrite(tasks,'data/raw/partd_download_tasks.csv')
 download_batch(tasks$url,tasks$file)
 for(y in selected_years) {
  rows<-tasks[year==y]
  dat<-rbindlist(lapply(rows$file,function(f) as.data.table(fromJSON(f))))
  stopifnot(nrow(dat)==st[year==y,expected],uniqueN(dat,by=c('Prscrbr_NPI','Brnd_Name','Gnrc_Name'))==nrow(dat))
  stopifnot(all(dat$Brnd_Name %in% brands))
  dat[,year:=y]
  fwrite(dat,sprintf('data/processed/partd_inhalers_%d.csv',y))
  cat('Verified Part D',y,nrow(dat),'rows\n')
 }
}
