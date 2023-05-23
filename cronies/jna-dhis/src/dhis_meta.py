import pandas as pd
import requests as rq
import drive as gd,re,json



class DHIS_Meta:

    def __init__(self,conf:object) -> None:
        self._base_url=conf.dhis_url
        element_map = gd.Drive(conf.drive_key).get_df(conf.e_map_google,'data_elements')
        self.__map=element_map.rename(columns={"element_id":"id","short_name":"shortName"})
        self.__map['description']=''


    def push_new_elements(self):
        template=pd.read_json('templates/data_element.json',orient='records')
        template=template[[x for x in template.columns if x not in self.__map.columns]]
        new=self.__map[self.__map.is_new=='new'][['name','shortName','description','id']]
        new=new.merge(template,how='cross').fillna('').to_dict(orient='records')
        return rq.post(f'{self._base_url}/api/metadata',json={"dataElements":new}).json()


    def add_category_combo(self):
        res=rq.get(f"{self._base_url}/api/categoryCombos?paging=false&fields=id~rename(categoryCombo),name~rename(comboName)").json()
        combos=pd.DataFrame(res.get('categoryCombos'))
        clean=lambda input:','.join(sorted(re.split(r'(?:\s+)?(?:,|and)(?:\s+)?',input))).replace(' ','_').lower()
        combos['comboName']=combos.comboName.apply(clean)
        self.__map['comboName']=self.__map.disaggregation.fillna('default').apply(clean)
        return self.__map.merge(combos,how='left',on='comboName')


    def update_dataset(self):
        datasets=[]
        for d in self.__map.dataset_id.unique():
            ds=rq.get(f'{self._base_url}/api/dataSets/{d}').json()
            tuma=lambda x:{
                'dataElement':{'id':x.id},
                'dataSet':{'id':d},
            }
            ds['dataSetElements']=self.__map[self.__map.dataset_id==d].apply(tuma,axis=1).to_list()
            datasets.append(ds)
        res=rq.post(f'{self._base_url}/api/metadata',json={'dataSets':datasets})
        if  res.status_code!=200 and res.status_code!=204:
            print(res.status_code,res.text)


    def __update_element(self,el):
        element={
                'id':el.id,
                'name':el.name,
                'shortName':el.shortName,
                'dataSet':el.dataset_id,
                'categoryCombo':el.categoryCombo
        }
        res=rq.patch(f'{self._base_url}/api/dataElements/{el.id}',json=element)
        if  res.status_code!=200 and res.status_code!=204:
            print(res.status_code,res.text)


    def update(self):
        self.push_new_elements()
        self.add_category_combo().apply(self.__update_element,axis=1)
        self.update_dataset()