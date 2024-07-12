import pandas as pd,sys,re,json
import requests as rq
import pkg_resources as pkg
from dihlibs import drive as gd,cron_logger as logger
from dihlibs import functions as fn

log=logger.get_logger_message_only()

class Meta:

    def __init__(self,dhis_url:str,map:pd.DataFrame) -> None:
        self._map=map.rename(columns={"element_id":"id","short_name":"shortName"})
        self._map=self._map[self._map.selection.isin(['new','update'])].copy().reset_index(drop=True)
        self._base_url=dhis_url
        self._map['description']=''

    def push_new_elements(self):
        file = pkg.resource_filename("dihlibs", "data/dhis_templates/data_element.json")
        template=pd.read_json(file,orient='records')
        template=template[[x for x in template.columns if x not in self._map.columns]]
        new=self._map[['name','shortName','description','id']].dropna(subset=['name','shortName'])

        new=new.merge(template,how='cross').fillna('').to_dict(orient='records')
        fn.text('payload.json',json.dumps(new,indent=2))
        res= rq.post(f'{self._base_url}/api/metadata',json={"dataElements":new})
        return res.json(); 

    def _normalize_combo(self, input):
        c = input.lower().strip()
        c = re.sub(r"(default(.+)|(.+)default)", r"\2\3", c)
        c = re.sub(r"(\d+)\D+(\d+)?\s*(yrs|year|mon|week|day)\w+", r"\1-\2\3", c)
        c = re.sub(r"(\d+)\D*(trimester).*", r"\1_\2", c)
        c = re.sub(r"(\W*,\W*|\Wand\W)", ",", c)
        c = re.sub(r"(\W*to\W*|\s+|\-)", "_", c)
        c = re.sub(r"_{2,}", "_", c)
        return ",".join(sorted([x.strip() for x in c.split(",") if x]))

    def add_category_combo(self):
        res=rq.get(f"{self._base_url}/api/categoryCombos?paging=false&fields=id~rename(categoryCombo),name~rename(comboName)").json()
        combos=pd.DataFrame(res.get('categoryCombos'))
        # clean=lambda input:','.join(sorted(re.split(r'(?:\s+)?(?:,|and)(?:\s+)?',input))).replace(' ','_').lower()
        combos['comboName']=combos.comboName.apply(self._normalize_combo)
        self._map['comboName']=self._map.disaggregation.fillna('default').apply(self._normalize_combo)
        return self._map.merge(combos,how='left',on='comboName')

    def update_dataset(self):
        datasets=[]
        for d in self._map.dataset_id.unique():
            ds=rq.get(f'{self._base_url}/api/dataSets/{d}').json()
            tuma=lambda x:{
                'dataElement':{'id':x.id},
                'dataSet':{'id':d},
            }
            ds['dataSetElements']=self._map[self._map.dataset_id==d].apply(tuma,axis=1).to_list()
            datasets.append(ds)
        res=rq.post(f'{self._base_url}/api/metadata',json={'dataSets':datasets})
        if  res.status_code!=200 and res.status_code!=204:
            log.error(res.status_code,res.text)


    def _update_element(self,el):
        element={
                'id':el.id,
                'name':el['name'],
                'shortName':el.shortName,
                'dataSet':el.dataset_id,
                'categoryCombo':el.categoryCombo
        }
        res=rq.patch(f'{self._base_url}/api/dataElements/{el.id}',json=element)
        if  res.status_code!=200 and res.status_code!=204:
            log.error(res.status_code,res.text)


    def update(self):
        self.push_new_elements()
        self.add_category_combo().apply(self._update_element,axis=1)
        self.update_dataset()