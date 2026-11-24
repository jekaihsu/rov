// Localized copy for career data files (contracts.json, licences.json, equipment.json).
// Stable keys are entity ids; Traditional Chinese source matches the JSON. UI reads through helpers in
// localize_data.js so game ids stay untranslated. Key scheme: career.copy.<bucket>.<id>.<field>
// (PROTOCOL.md “前端依穩定 key 翻譯”).
import { localize } from '../i18n/index.js';

const STRINGS = localize('career.copy', {
  clients: {
    yx: {
      label: "YX 海事服務"
    },
    harbor: {
      label: "青嶼港務局"
    },
    shipping: {
      label: "船東與船管"
    },
    marine_works: {
      label: "堤岸工程"
    },
    aquaculture: {
      label: "養殖業者"
    }
  },
  jobs: {
    training: "公司內訓",
    checkout: "下水檢查潛",
    familiarization: "開放水域熟悉",
    gvi: "一般目視檢查（GVI）",
    marine_growth: "海生物量測（Level II）",
    fouling: "船殼附著評級",
    search: "搜尋與確認",
    cp: "陰極防蝕量測（CP）",
    ut: "超音波測厚（UT）",
    net: "網衣巡檢",
    recovery: "回收作業",
    mooring: "繫泊檢查"
  },
  chapters: {
    prologue: {
      title: "序章 · 見習之前",
      summary: "公司水池與開放水域：把基本功練熟，拿下見習駕駛員執照。"
    },
    ch1: {
      title: "第一章 · 港口與船舶",
      summary: "在濁水與船底下方交出可用報告；學會被客戶催的時候仍守程序。章末交班窗口是二級駕駛員考核。"
    },
    ch2: {
      title: "第二章 · 養殖場",
      summary: "外海箱網：網衣、死魚與繫泊。需要二級駕駛員執照。"
    }
  },
  contracts: {
    p0_induction: {
      title: "新人內訓：水池操作課",
      clientName: "YX 海事服務 · 訓練",
      summary: "馬力陪飛。到北牆觀察鬆桿時的深度變化，再拍三面標板。",
      brief: "青嶼港訓練池，淡水、無流。周楷看纜，馬力帶飛。依次帶回北、東、南三面標板的照片，由林岑點收。",
      radio: {
        speaker: "林岑",
        start: "向潮－指揮呼叫 R-1。今天池裡認識搭檔。先檢查。",
        done: "收工。程序過了。"
      },
      deliverables: {}
    },
    p1_pool_checkout: {
      title: "水池檢查潛",
      clientName: "YX 海事服務 · 訓練",
      summary: "水池檢查潛：解鎖、懸停、三面池壁各拍一張、回投放點。約 15–20 分。",
      brief: "工單 YX-TR-001。載具 YX Model R。完成預潛檢查表後入水；解鎖推進器，池中央懸停 20 秒，北、東、南三面池壁各拍一張帶疊字照片，最後回投放點等回收。水面外禁止解鎖。",
      radio: {
        speaker: "林岑",
        start: "入水。人離甲板再解鎖。",
        done: "照片夠了。準備回收。",
        partial: "人機回來就好。重跑本趟。"
      },
      deliverables: {
        unlock: "解鎖推進器",
        hover: "池中央懸停 20 秒（偏移 < 0.6 m）",
        photo_north: "北池壁照片",
        photo_east: "東池壁照片",
        photo_south: "南池壁照片",
        depth_hold: "定深功能確認",
        recover: "回投放點，準備回收"
      }
    },
    p2_open_water: {
      title: "開放水域熟悉（見習考核）",
      clientName: "YX 海事服務 · 訓練",
      summary: "見習考核：四個浮標檢查點、定深、鬆桿看漂移。全程真實模式。約 15–20 分。",
      brief: "工單 YX-TR-002。青嶼港外避風水域。依序通過四個檢查點，定深保持，途中鬆桿觀察漂移再穩住，回投放點。微流；推力不等於速度。考核強制真實設定。通過後頒發見習駕駛員執照。",
      radio: {
        speaker: "林岑",
        start: "R-1，四個浮標檢查點。依序。",
        done: "熟悉夠了。回船。",
        partial: "回來對。重跑熟悉趟。"
      },
      deliverables: {
        unlock: "解鎖推進器",
        cp1: "檢查點 1",
        depth_hold: "開啟定深",
        cp2: "檢查點 2",
        drift: "懸停 15 秒，觀察漂移",
        cp3: "檢查點 3",
        cp4: "檢查點 4",
        recover: "回投放點上浮"
      }
    },
    c1_pier_level1: {
      title: "碼頭外的第一張工單",
      clientName: "青嶼港務局",
      summary: "Level I 巡視：棧橋六根樁各拍一張樁身照，纜線不要繞樁。",
      brief: "青嶼港務局要在颱風季前做一次 Level I 巡視，只要覆蓋、不要量測。棧橋下 A、B 兩列共六根樁，每根在水深約 6 m 拍一張樁身照，看得到樁就算。橫流偏東，繞樁前先想好怎麼退，回收時纜線不能纏在樁上。碼頭壁面有空就順手拍一張，港務局會很感激（但不會多付錢）。",
      radio: {
        speaker: "林岑",
        start: "第一張外面的單子。周楷在甲板看線，你專心看樁。",
        done: "港務局說照片很清楚。他們以前收過一整卷只拍到泥巴的。",
        partial: "先交這些。剩下的樁我跟葉理說改天補。"
      },
      deliverables: {
        pile_a1: "A 列 1 號樁",
        pile_a2: "A 列 2 號樁",
        pile_a3: "A 列 3 號樁",
        pile_b1: "B 列 1 號樁",
        pile_b2: "B 列 2 號樁",
        pile_b3: "B 列 3 號樁",
        quay: "碼頭壁面概況（加分）",
        recover: "回投放點回收"
      }
    },
    c1_pier_level2: {
      title: "碼頭 Level II 抽樣：海生物量測",
      clientName: "青嶼港務局／葉理",
      summary: "碼頭 B 區指定 3 根樁 × 3 高程，用雷射比例尺量海生物厚度；低能見度約 1.5 m。",
      brief: "工單編號：YX-HB-024\n客戶：青嶼港務局／葉理\n地點：碼頭 B 區指定 3 根樁\n載具：YX Model R＋雷射比例尺（若未解鎖：本關引導解鎖或借用隊上尺）\n工作內容：Level II 抽樣\n  - 3 樁 × 3 高程量海生物厚度（誤差門檻見任務參數）\n  - 每點選軟／硬附著\n  - 離樁距離約 0.7×能見度\n海況：低能見度約 1.5 m；港內流\n注意：漏量任一點不能交件；燈太亮會背向散射",
      radio: {
        speaker: "葉理",
        start: "岸台－葉。三根樁，要厚度數字。",
        done: "數字進來就簽。",
        partial: "缺點改期補。先交能交的。"
      },
      deliverables: {
        a1_upper: "A1 樁 · 水深 4 m",
        a1_lower: "A1 樁 · 水深 12 m",
        a3_upper: "A3 樁 · 水深 4 m",
        a3_lower: "A3 樁 · 水深 12 m",
        b2_upper: "B2 樁 · 水深 4 m",
        b2_lower: "B2 樁 · 水深 12 m",
        b2_photo: "B2 樁附著層近照（加分）",
        recover: "回投放點回收",
        a1_d4: "A1 樁 · 水深 4 m",
        a1_d8: "A1 樁 · 水深 8 m",
        a1_d12: "A1 樁 · 水深 12 m",
        a3_d4: "A3 樁 · 水深 4 m",
        a3_d8: "A3 樁 · 水深 8 m",
        a3_d12: "A3 樁 · 水深 12 m",
        b2_d4: "B2 樁 · 水深 4 m",
        b2_d8: "B2 樁 · 水深 8 m",
        b2_d12: "B2 樁 · 水深 12 m"
      }
    },
    c1_hull_fouling: {
      title: "貨輪船殼附著評級",
      clientName: "北灣船管（葉理轉介）",
      summary: "青嶼港池靠泊貨輪「青嵐」：確認 LOTO 後拍 niche 與平底航線，附著評級 0–4。",
      brief: "工單編號：YX-HL-008\n客戶：北灣船管（窗口由葉理轉介）\n地點：青嶼港池靠泊貨輪「青嵐」（虛構船名）\n載具：YX Model R\n工作內容：\n  - 確認 LOTO：主機／螺槳／側推／海水泵已停用\n  - niche areas：海底門×2、舵、螺槳、測深換能器各 1 張＋附著評級 0–4\n  - 平底兩條航線覆蓋\n海況：能見度約 3 m；船底下方無水面參考\n注意：未確認 LOTO 靠近螺槳＝安全失敗；纜易卡舭龍骨",
      radio: {
        speaker: "林岑",
        start: "LOTO 確認了嗎？",
        done: "船管要評級表。轉給我。",
        partial: "有拍到的先交，螺槳那邊下次再來。"
      },
      deliverables: {
        keel_starboard: "右舷舭龍骨（加分）",
        keel_port: "左舷舭龍骨（加分）",
        loto: "確認 LOTO：主機／螺槳／側推／海水泵",
        propeller: "螺槳葉片",
        rudder: "舵",
        recover: "回投放點回收",
        seachest_fwd: "前海底門",
        seachest_aft: "後海底門",
        transducer: "測深換能器",
        flat_port: "平底左舷航線",
        flat_starboard: "平底右舷航線"
      }
    },
    c1_dropped_object: {
      title: "港內掉落物",
      clientName: "堤岸工程",
      summary: "濁水港池：成像聲納格網搜尋掉落測量儀，影像確認後標記交潛水員。",
      brief: "工單編號：YX-SR-003\n客戶：堤岸工程\n地點：港池指定 50×50 m 搜尋區\n載具：YX Model R＋成像聲納（解鎖本關）；夾爪可選\n工作內容：\n  - 聲納格網搜尋掉落測量儀\n  - 影像確認後原位拍照\n  - 掛回收繩或標記交潛水員（依裝備：有夾爪則掛繩）\n海況：濁水；泥底易揚沙\n注意：30 分內未找到可中止交搜尋紀錄（銅）；勿移動前未拍照",
      radio: {
        speaker: "林岑",
        start: "聲納先。眼睛後。",
        done: "座標收到。謝了。",
        partial: "可中止。交搜尋紀錄。"
      },
      deliverables: {
        contact: "以聲納找到回波並接近",
        confirm_photo: "相機確認：測量儀",
        recover: "回投放點回收",
        mark: "標記交潛水員／掛回收繩",
        lift: "夾爪掛繩提離（若有夾爪）"
      }
    },
    c1_quay_cp: {
      title: "碼頭鋼板樁防蝕抽測",
      clientName: "青嶼港務局",
      summary: "支線：碼頭壁三個點用 CP 探針頂住讀電位，找出保護不足的地方。",
      brief: "港務局對我們有點信心了，追加一張小單：碼頭壁三個抽測點量陰極防蝕電位。探針要輕輕頂住壁面、停穩幾秒才有讀數；撞上去讀數不算，還會被扣分。讀數比 −800 mV 正的地方就是保護不足，報告裡要標出來。",
      radio: {
        speaker: "林岑",
        start: "這次是要你碰它，但要溫柔地碰。",
        done: "第三點保護不足，葉理會安排換陽極。很好的發現。",
        partial: "先交這兩點。"
      },
      deliverables: {
        cp_west: "碼頭壁 南段 · 水深 6 m",
        cp_mid: "碼頭壁 中段 · 水深 10 m",
        cp_east: "碼頭壁 北段 · 水深 6 m",
        recover: "回投放點回收"
      }
    },
    c1_hull_ut: {
      title: "船殼測厚抽點",
      clientName: "北灣船管",
      summary: "支線：船殼舷側四個點用超音波測厚，船級年檢要用。",
      brief: "北灣船管的船級年檢需要舷側抽點測厚。左右舷、船中前後各一點，水深約 4 m。探頭要貼住鋼板、停穩，讀數才可信。這次不靠近螺槳，但船底下面一樣沒有水面參考。",
      radio: {
        speaker: "周楷",
        start: "四個點，量完就收工。今天甲板便當是排骨。",
        done: "都在容許範圍內。驗船師會很開心，船東會更開心。",
        partial: "缺的點驗船師會再要，先交。"
      },
      deliverables: {
        ut_sb_fwd: "右舷 船中前",
        ut_sb_aft: "右舷 船中後",
        ut_ps_fwd: "左舷 船中前",
        ut_ps_aft: "左舷 船中後",
        recover: "回投放點回收"
      }
    },
    c1_signoff_exam: {
      title: "章末：交班前趕工複查（二級考核）",
      clientName: "青嶼港務局／葉理",
      summary: "交班窗口：複查三處異常是否惡化，盡量同角度重拍；程序與安全高於準時。",
      brief: "工單編號：YX-HB-031（緊急加開）\n客戶：青嶼港務局\n地點：碼頭 A／B 交接區，上次報告之 3 處異常\n載具：YX Model R\n工作內容：\n  - 交班前複查 3 個異常是否惡化\n  - 每處盡量與上次同角度重拍\n  - 潮／靠泊窗口有限；可中止並註明未完成項\n海況：午後風起；能見度轉差\n注意：葉理要檔案才能交班；程序與安全高於準時",
      radio: {
        speaker: "林岑",
        start: "R-1，只打三點異常。",
        done: "收工。見習結束考核過。",
        partial: "中止。窗不夠。"
      },
      deliverables: {
        a2_crack: "A2 樁 · 水深 10 m 裂痕",
        b3_spall: "B3 樁 · 水深 14 m 剝落",
        quay_chip: "碼頭壁南段 · 水深 12 m 缺角",
        quay_station: "碼頭壁中段 · 定點目視 6 秒",
        recover: "回投放點回收",
        anomaly_extra: "未列異常：旁縫（加分）"
      }
    },
    c2_net_inspection: {
      title: "網衣巡檢",
      clientName: "東澳外海箱網場",
      summary: "平潮時沿箱網外側繞一圈，找出兩個網衣破洞並拍照。靠太近推進器會吸網。",
      brief: "場長說最近每天少魚，懷疑網衣破了。趁平潮從網外側繞一圈（東、北、西、南四個方位都要經過），看到破洞就停下來正對拍照。不要貼網太近，推進器會把網衣吸過來；纜線也別跨過繫泊纜。",
      radio: {
        speaker: "場長 阿美",
        start: "魚很怕生，你慢一點，牠們就不會亂跑。",
        done: "兩個洞都找到了，今天下午就補。謝謝你們。",
        partial: "先補找到的這個，剩下的明天平潮再看。"
      },
      deliverables: {
        ring_south: "南側網外（水深 7 m）",
        ring_east: "東側網外",
        ring_north: "北側網外",
        ring_west: "西側網外",
        hole_upper: "破洞 · 水深約 7 m",
        hole_lower: "破洞 · 水深約 13 m",
        recover: "回投放點回收"
      }
    },
    c2_mort_recovery: {
      title: "死魚回收（Model V）",
      clientName: "東澳外海箱網場",
      summary: "從網邊走道把 Model V 放進網內，用夾爪把網底的死魚夾起來。需要機械臂，只能派 Model V。",
      brief: "網底積了幾尾死魚，放著會壞水質。這次從箱網走道直接把機子放進網內，只有 Model V 有機械臂，所以派它。下到網底，一尾一尾夾起來提離網底；夾住以後配平會變，慢慢來，碰網底會驚動整箱魚。",
      radio: {
        speaker: "場長 阿美",
        start: "這工作不好看，但很重要。",
        done: "網底乾淨多了。下次請你吃魚，活的那種。",
        partial: "先收這些，剩下的我們用撈網。"
      },
      deliverables: {
        first_fish: "夾起一尾死魚並提離網底",
        second_fish: "再回收一尾（加分）",
        recover: "回到網內下水點回收"
      }
    },
    c2_mooring_exam: {
      title: "章末：颱風過後的錨繩（箱網簽注考核）",
      clientName: "東澳外海箱網場",
      summary: "沿南側兩條錨繩從浮標看到錨，記錄錨繩狀況。全程真實模式。",
      brief: "颱風剛過，場長要確認繫泊還撐得住。從東南、西南兩個角浮標下去，沿錨繩一路看到錨，錨繩中段各拍一張狀況照。自己的纜線不要跨過錨繩。這是箱網作業簽注的考核。",
      radio: {
        speaker: "林督導",
        start: "湧浪會讓你上下晃，那是正常的，不是你的錯。",
        done: "簽注下來了。你現在是養殖場會指名的駕駛員。",
        partial: "還差一點，等下一個平潮再考。"
      },
      deliverables: {
        east_buoy: "東南角浮標下方",
        east_line: "東南錨繩中段",
        east_anchor: "東南錨",
        west_buoy: "西南角浮標下方",
        west_line: "西南錨繩中段",
        west_anchor: "西南錨",
        recover: "回投放點回收"
      }
    }
  },
  grades: {
    none: {
      label: "學員（未持照）",
      short: "學員",
      opens: "公司內訓與水池檢查潛"
    },
    trainee: {
      label: "見習駕駛員",
      short: "見習",
      opens: "港內簡單檢查：碼頭 Level I、船殼、港內搜尋"
    },
    grade2: {
      label: "二級駕駛員",
      short: "二級",
      opens: "碼頭與船殼細部檢查、養殖場"
    },
    grade1: {
      label: "一級駕駛員",
      short: "一級",
      opens: "搜救、水庫、離岸風電（後續章節）"
    },
    senior: {
      label: "資深駕駛員",
      short: "資深",
      opens: "海纜、夜間、多機（後續章節）"
    },
    supervisor: {
      label: "主管",
      short: "主管",
      opens: "作業級任務的監看與指揮（後續章節）"
    }
  },
  endorsements: {
    aquaculture: {
      label: "箱網作業簽注"
    }
  },
  items: {
    laser_scaler: {
      label: "雷射比例尺",
      use: "兩道平行雷射點打在目標上，影像裡就有已知間距，可以量尺寸。",
      unlocks: "海生物厚度、缺陷尺寸等量測交付（Level II 工單）"
    },
    imaging_sonar: {
      label: "成像聲納",
      use: "能見度不足時以聲波成像找目標與結構，再用相機確認。",
      unlocks: "港內掉落物等搜尋工單"
    },
    cp_probe: {
      label: "陰極防蝕（CP）探針",
      use: "探針頂住鋼構，讀取對參考電極的電位，判斷防蝕是否足夠。",
      unlocks: "鋼板樁、鋼構的 CP 量測交付"
    },
    ut_gauge: {
      label: "超音波測厚儀（UT）",
      use: "探頭貼住鋼板量剩餘壁厚，找出腐蝕減薄處。",
      unlocks: "船殼與鋼構的測厚交付"
    },
    gripper: {
      label: "作業夾爪套件",
      use: "YX Model V 機械臂的作業夾爪與收集籃，回收類工單的標準配備。",
      unlocks: "死魚、掉落物等回收工單"
    },
    sticker_yx_logo: {
      label: "YX 公司標誌貼紙",
      use: "機身兩側的 YX 標誌。客戶在甲板上一眼就知道是誰家的機子。"
    },
    sticker_yx_stripe: {
      label: "YX 橘白塗裝條紋",
      use: "公司船隊的橘白斜紋，在混水裡比較好找。"
    }
  }
});

export const COPY = STRINGS;
