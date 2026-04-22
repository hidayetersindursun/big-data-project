ürkiye yazıcaz turkey değil

referans yok

Bu tarz bir ürün var mı
Tedarik devri

Domatesin mesela son 10 seneki olayı

Arhciyecture da structured bilgisi

Apache nifi airflow yerine
Airflow hazır yok biz kurabiliriz

Bronza girince veri nr kadar küçülcek

Metadolohş yok 

tf idf e falan girme hiç doc to vec
Dil modelş kullan geç 

Athena elastic search



Emr oc açıtoyum 500gb veriyi şu kadarda işlerim diyebileceğiz

Pandemi öncesi sonrası gap açılıyo mu zary zury

Facebook olayı

Domates fiyatı zaman serisi
Teknik olarak nereye entegre edebiliriz.

Airflow apache nifi kullan
Airflow kendin kurabilirsin, hazır kullanamazsın

Bronze parquet fomat

1/40 düşüyor şu kadar oluyor şuradan su kadar veri geçiyor 

Athena yerine elk kullanicaz

Metodoloji yok

Tf idf eski (qwen 3.5 modeli yapın)

Doc2vec
Word2vec

5 gb idi mesela
200 gelse olurum
Emr açacaksınız denicez orada 
Büyük veri ile basetme

Nifi ile batchler halinde sürekli process eden bir pipeline

Shcok index
Gap genişliyor mu, neden genişliyor mu

Prophet meta

sunum fontu büyük olsun bi dahakine

referans koyun

her şey AWS de olacak ona göre toolları seçin

çok data var kardeşim: millet data crawler yazzıyor, sentetik yapıyor, trendyoldan 2tb lık data alan öğrencileri bile varmış.

google news data

data alıcan parquet yapıcan işlicen falan filan

literatür search yapmak lazım bizim konuda. dünyada nasıl yapmışlar bizim projeyi.

bizimkini yapan agalar:
• epey bb saydılar hal verileri için
• sentinel 2 l2a data ile ndvi indexi kullanacaklarmış. crop canlı mı onu hesaplayan bişi. (buradan bakıp don oldu mesela nasıl yansıyacak)
• GDELT news için, 15 dk da bir. Turkey, agriculture vb. şeyler filtreliceklermiş, haber, export ban vb.
• weather data, openmeteo historical api, saatlik, soil moisture,vb şeyler varmış. frost ve heat stress var mesela.
•  transportation cost
• tüik tmcb, tarım üfe, usdtry, 

* xgboost ve lstm ile train

* ilk önce plot bölge seçin sonra tüm de denersiniz dedi.
* ankara konya, ana yollardaki trafik etki ediyor mu. istanbul izmir, orada ekinler var etki ediyor mu (tam anlamadım burayı)

AI assist kullanıldı disclaimer ekle
Sunuma referans ekle
Turkey leri türkiye yap
Bununla ilgili ürün var mı araştırın ? 
10-35 kısmını kategorilere bölelim domates mi başka neler var
Data source kısmına 
Airflow yerine apache nifi ? Kullanacakmışız
Airflowu kendimiz kurabiliriz ama hazır alamayxağız
Bronze için parquet formatını altına yazalım
200gb yi parquet e geçirnce düşecek, onu gösterelim istedi
Athena yerine elastic search k kullancsz
Qwen modelinş alıp dump edin
Doc2vec kullan tf idf yerine
Word2vec 
Verisetini parça parça alırken 21 pc açıyorum beklentim 5dk içinde process edip kapatmak
Nifi ile sürekli process eden pipelinr gösterebiliriz
Pandemi öncesi sonrası domates fiyatının değişimi, 
Propet ile timeseries gelecek tahmini
sunumdaki yazılar ufak okunabilir olmalı


derste söyledikleri:

önceliğimiz EC2
• micro small nano medium makina dışına açmayın 
• s3
• emr (şu anda değil)

kademe kademe verileri s3 e taşı
boto/boto3 ile s3 e api üzerinden bağlanabiliriz.