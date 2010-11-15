<?php 
/*
 * index.php --  this is part of a web interface for UNO-darmstadt
 *
 * Copyright 2009,2010 Arun Persaud
 *
 * ------------------------------------------------------------------------
 *
 * UNO-darmstadt is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or (at
 * your option) any later version.
 *
 * UNO-darmstadt is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program. If not, see http://www.gnu.org/licenses/.  *
 *
 * ------------------------------------------------------------------------
 *
 *  wep-page:
 *     http://uno-darmstadt.sourceforge.net
 *
 *  It would be nice to get some feedback (bugs or other comments), so please drop
 *  me a line if you are using UNO-darmstadt :)
 *  have fun
 *        Arun
 */

include('config.php');
include('include/functions.php');

error_reporting(E_ALL);

output_header('svg');

/* open database - always needed */
DB_open($DB_HOST,$DB_USER,$DB_PASSWD,$DB_DB);

/* how many games must a person have played, so that we will show it in the statistics */
$options="";

if(isset($_REQUEST["mingames"]))
  {
    $mingames=$_REQUEST["mingames"];
  }
 else
   { 
     $mingames=0;
   };
$options.="mingames=$mingames";

if(isset($_REQUEST["groupsize"]))
  {
    $groupsize=$_REQUEST["groupsize"];
  }
 else
   {
     $groupsize=0;
   }; 
$options.="&amp;groupsize=$groupsize";

?>

<div class="nav">
<?php
/*************************************
 *
 * List recent players in the database
 *
 *************************************/

$datatmp = mysql_query("SELECT players.name, MAX(scores.id) as maxscore FROM scores ".
		       "   LEFT JOIN players ON players.id=scores.player ".
		       "   GROUP BY players.name".
		       "   ORDER BY maxscore DESC".
		       "   LIMIT 20");
?>

<div class="names">
<h2>recent Players</h2>
<p> list <a href="index.php?allplayers=1">all players</a> in the database. </p>
<ul>
<?php
while($who = mysql_fetch_array($datatmp, MYSQL_NUM))
  echo "<li><a href=\"index.php?name=".$who[0]."\">".$who[0]."</a></li>\n";
?>
</ul>
</div>
<?php
/***************************
 *
 *            Menu
 *
 ****************************/
?>
<div class="menu">

<ul>
<?php
echo "
<li> <a href=\"index.php?".$options."\">  Home </a> </li> 
<li><a href=\"index.php?total=games&amp;".$options."\">         all games      </a> </li>
<li><a href=\"index.php?total=movingaverage&amp;".$options."\"> moving average </a> </li>\n"; ?>
<li><a href="index.php?games=all"> all sessions</a></li>
<li><a href="index.php?lowest=1">  low  scoring sessions</a> </li>
<li><a href="index.php?highest=1"> high scoring sessions</a> </li>
<li><a href="data-input.php"> Admin </a> </li>
</ul>

<br />

<?php
 echo "<form action=\"index.php" ;
if(isset($_REQUEST["total"]))
  echo "?total=".$_REQUEST["total"]."";
else if(isset($_REQUEST["games"]))
  echo "?games=".$_REQUEST["games"]."";
else if(isset($_REQUEST["lowest"]))
   echo "?lowest=1";
else if(isset($_REQUEST["highest"]))
   echo "?highest=1";
echo "\" method=\"post\">\n";
echo "<fieldset> <legend> Options</legend>";
echo " <p>include only people with a minimum number:
         <input name=\"mingames\" type=\"text\" size=\"3\" maxlength=\"3\" value=\"$mingames\" /> 
         games (0 for no minimum)</p>
       <p>include only session with 
         <input name=\"groupsize\" type=\"text\" size=\"3\" maxlength=\"3\" value=\"$groupsize\" /> players (0 for all)</p>
       <input type=\"submit\" value=\"update\" />";
echo "</fieldset>
</form>\n";

echo "</div>\n";
?>

</div>

<div class="rest">
<?php
/*************************************
 *
 * List all players in the database
 *
 *************************************/
?>
<?php
if(isset($_REQUEST["allplayers"]))
  {
    $datatmp = mysql_query("SELECT name FROM players ORDER BY name");
?>

<div class="allplayers">
<h2>Players</h2>
<p>
You can also try out the following: click on one of the names, 
go to the url and change the 'name=X' part into 'name=X:Y:Z:... ', 
e.g. http://ebit....index.php?name=Frances:Theresa
</p>
<ul>
<?php
while($who = mysql_fetch_array($datatmp, MYSQL_NUM))
  echo "<li><a href=\"index.php?name=".$who[0]."\">".$who[0]."</a></li>\n";
?>
</ul>
</div>
<?php
/******************************
 *
 * Player statistics
 *
 *******************************/
}
 else if(isset($_REQUEST["name"]))
   {
     /* do individual statistics */
     
     /* get the min/max number of players */
     $Nmax = mysql_query("SELECT max(number_of_players) FROM session ");
     $Nmax = mysql_fetch_array($Nmax, MYSQL_NUM);
     $Nmax = $Nmax[0];
     
     $Nmin = mysql_query("SELECT min(number_of_players) FROM session ");
     $Nmin = mysql_fetch_array($Nmin, MYSQL_NUM);
     $Nmin = $Nmin[0];
     
     
     $namestring = $_REQUEST["name"];
     $names = explode(":",$namestring);
     echo "<div class=\"person\">\n";
     echo "<h3>$namestring</h3>\n\n";
     
     
     /* distribution of points */
     echo "<div class=\"person-graph\">\n";
     
     echo "<svg:svg  version=\"1.1\" baseProfile=\"full\" width=\"500px\" height=\"200px\" >\n";
     echo "<svg:rect class=\"bg\" x=\"0px\" y=\"0px\" width=\"500px\" height=\"200px\"  />\n";
     
     foreach($names as $key=>$name)
       {
	 $data = mysql_query("SELECT id FROM players WHERE name=".DB_quote_smart($name));
	 $nameid = mysql_fetch_array($data, MYSQL_NUM);
	 $nameid=$nameid[0];
	 
	 $ydata = array();
	 
	 $datatmp = mysql_query( "SELECT SUM(case when scores.player='$nameid' then scores.score else '0' end),".
				 "max(case when scores.player='$nameid' then case when scores.score='-' then 0 else scores.score end else '-1' end)".
				 " FROM scores LEFT JOIN  games ON games.id=scores.game LEFT JOIN session ON session.id=games.session ".
				 " group by scores.game ORDER BY session.date DESC");
	 $data=array();
	 while($dat = mysql_fetch_array($datatmp, MYSQL_NUM))	   
	   $data[]=$dat;
	 
	 $num=10;
	 for($i=0;$i<count($data)-$num; $i++)
 	   {
 	     $tmp=0;
 	     $stop=$num;
 	     for($j=0;($j<$stop)&&($j<count($data)-$i); $j++)
 	       if($data[$i+$j][1]<0) 
 		 $stop++; //didn't play in that session
 	       else
 		 $tmp+=$data[$i+$j][0];
 	     if($data[$i][1]<0) 
 	       $ydata[]=0;
 	     else
 	       $ydata[]=$tmp/$num;
 	   };
	 
	 // so that the plot have all the same x-axis, we just fill the rest with zeros
	 for(;$i<count($data); $i++)
 	   $ydata[]=0;
	 echo "<svg:path class=\"singleperson".fmod($key,3)."\" d=\"M0,200 L \n";
	 $c=count($ydata);
	 $m=max($ydata);
	 $x=0;$y=0;
	 foreach ($ydata as $ketmpy=>$value)
	   {
	     $x=$x+490/$c;
	     $y=200-$value/$m*180;
	     echo " ",round($x,1)," ",round($y,2)," \n";
	   };
	 echo "Z M".(10+30*fmod($key,3)).",10 L ".(30+30*fmod($key,3))." 10 ".(30+30*fmod($key,3))." 30 ".(10+30*fmod($key,3))." 30 Z\"  />\n";
	 
       };
     
     echo "</svg:svg>\n";
     echo "</div>\n";
     
     
     
     /* overall statistics */
     echo "<div class=\"games\">\n";
     echo "<table>\n";
     echo "<thead><tr><th>Name</th><th>Points</th><th>Average</th><th>Sigma</th><th>Number of Games </th><th>Wins</th></tr></thead>\n";
     echo "<tbody>\n";
     foreach($names as $name)
       {
	 $datatmp = mysql_query("SELECT sum(IF(score<0,0,score)),".
				"       avg(IF(score<0,0,score)),".
				"       std(IF(score<0,0,score)),".
				"       count(*) FROM scores LEFT JOIN players ON players.id=scores.player WHERE players.name=".DB_quote_smart($name));
	 $data    = mysql_fetch_array($datatmp, MYSQL_NUM);      
	 
	 $winstmp = mysql_query("SELECT count(*) FROM scores LEFT JOIN players ON players.id=scores.player ".
				"WHERE players.name=".DB_quote_smart($name)." AND scores.score='-1'");
	 $wins    = mysql_fetch_array($winstmp, MYSQL_NUM);      
	 
	 echo "<tr><td>$name</td><td>".$data[0]."</td>\n";
	 if(sizeof($names)==2)
	   if($name==$names[0])
	     $av1=$data[1];
	   else
	     $av2=$data[1];
	 echo "<td>".round($data[1],2)."</td>\n";
	 echo "<td>".round($data[2],2)."</td>\n";
	 echo "<td>".$data[3]."</td>\n";
	 if($data[3])
	   echo "<td>".$wins[0]." (=".round(100*$wins[0]/$data[3],2)."%)</td></tr>\n";
	 else
	   echo "<td>".$wins[0]."</td></tr>\n";
       }
     echo "</tbody></table>\n";
     echo "</div>\n";
     /* print averages vs. groupsize */
     foreach($names as $name)
       {
	 echo "<div class=\"games\">\n ";
	 if(sizeof($names)>1) echo "<h4> $name </h4>\n";
	 echo "<table>\n";
	 echo "<thead><tr><th>Groupsize</th><th>Points</th><th>Average</th><th>Sigma</th><th>Number of Games </th><th>Wins</th></tr></thead>\n";
	 echo "<tbody>";
	 for($N=$Nmin;$N<$Nmax;$N++)
	   {
	     $datatmp = mysql_query("SELECT sum(IF(score<0,0,score)),".
				    "       avg(IF(score<0,0,score)),".
				    "       std(IF(score<0,0,score)),".
				    "       count(*)".
				    " FROM scores ".
				    "   LEFT JOIN players ON players.id=scores.player ".
				    "   LEFT JOIN games   ON   games.id=scores.game ".
				    "   LEFT JOIN session ON session.id=games.session ".
				    "  WHERE players.name=".DB_quote_smart($name)." AND session.number_of_players=$N ");
	     $data    = mysql_fetch_array($datatmp, MYSQL_NUM);      
	     
	     $winstmp = mysql_query("SELECT count(*) FROM scores ".
				    "   LEFT JOIN players ON players.id=scores.player ".
				    "   LEFT JOIN games   ON   games.id=scores.game ".
				    "   LEFT JOIN session ON session.id=games.session ".
				    "WHERE session.number_of_players=$N AND scores.score='-1' AND  players.name=".DB_quote_smart($name));
	     $wins    = mysql_fetch_array($winstmp, MYSQL_NUM);      
	     
	     echo "<tr><td>$N</td>";
	     echo "<td>".$data[0]."</td>\n";
	     echo "<td>".round($data[1],2)."</td>\n";
	     echo "<td>".round($data[2],2)."</td>\n";
	     echo "<td>".$data[3]."</td>\n";
	     if($data[3])
	       echo "<td>".$wins[0]." (=".round(100*$wins[0]/$data[3],2)."%)</td></tr>\n";
	     else
	       echo "<td>".$wins[0]."</td></tr>\n";
	   };
	 echo "</tbody></table>\n</div>\n";
       };
     
     
     if(sizeof($names)==2)
       {
	 // do analysis of who sits so and so many places away from person a, to get rid of that rumor once and for all ;)
	 echo "<div class=\"rumor\">\n";
	 echo "<h1>Anti - Rumor for ".$names[0]." ".$names[1]."</h1>\n<p> red means above the overall average, green below</p>";
	 mysql_query("CREATE TEMPORARY TABLE rumor AS SELECT scores.game as game,".
		     "SUM(CASE WHEN players.name='".$names[0]."' THEN scores.position ".
		     "when players.name='".$names[1]."' THEN -scores.position ". 
		     "else '0' END) AS diffpos,".
		     "SUM(CASE WHEN players.name='".$names[0]."' THEN scores.position+1 ".
		     "ELSE '0' END) AS play1played,".
		     "SUM(CASE WHEN players.name='".$names[1]."' THEN scores.position+1 ". 
		     "ELSE '0' END) AS play2played,".
		     "SUM(CASE WHEN players.name='".$names[0]."' THEN IF(scores.score<0,0,scores.score) ".
		     "ELSE '0' END) AS play1score,".
		     "SUM(CASE WHEN players.name='".$names[1]."' THEN IF(scores.score<0,0,scores.score) ". 
		     "ELSE '0' END) AS play2score,".
		     "session.number_of_players AS Nplayers ".
		     "FROM scores ".
		     "LEFT JOIN games   ON   games.id=scores.game ".
		     "LEFT JOIN session ON session.id=games.session ".
		     "LEFT JOIN players ON scores.player=players.id ".
		     "GROUP BY scores.game ORDER BY games.id DESC");
	 
	 echo "<table border='1'>";
	 echo "<thead>
  <tr>
  <td>total number of players</td>
  <td>".$names[0]."</td>
  <td>".$names[1]."</td>
  <td> position </td><td>number of games</td>
  </tr></thead><tbody>\n";
	 for($N=2;$N<$Nmax;$N++)
	   {
	     $datatmp = mysql_query("SELECT AVG(play1score),".
				    "       AVG(play2score),".
				    "       IF(diffpos<0,diffpos+Nplayers,diffpos) as newdiff,".
				    "       count(*) ".
				    "FROM rumor ".
				    "WHERE play1played<>0 AND play2played<>0 AND Nplayers=$N ".
				    "GROUP BY newdiff ".
				    "ORDER BY newdiff");
	     while($dat = mysql_fetch_array($datatmp, MYSQL_NUM))
	       {
		 $d0 = $dat[0];
		 $d1 = $dat[1];
		 $d3 = $dat[2];
		 $d4 = $dat[3];
		 echo "<tr> <td>$N</td>";
		 if($d0>$av1)
		   echo "<td bgcolor='#cc3333'>";
		 else
		   echo "<td bgcolor='#33cc33'>";
		 echo round($d0,2)."</td>";
		 if($d1>$av2)
		   echo "<td bgcolor='#cc3333'>";
		 else
		   echo "<td bgcolor='#33cc33'>";
		 echo round($d1,2)."</td><td> $d3 </td><td> $d4 </td></tr>\n";
	       }
	   }
	 $datatmp = mysql_query("SELECT AVG(play1score),".
				"       AVG(play2score),".
				"       IF(diffpos<0, diffpos+Nplayers, diffpos) as newdiff,".
				"       count(*)".
				"FROM rumor ".
				"WHERE play1played<>0 AND play2played<>0 ".
				"GROUP BY newdiff ".
				"ORDER BY newdiff");
	 while($dat = mysql_fetch_array($datatmp, MYSQL_NUM))
	   {
	     $d0 = $dat[0];
	     $d1 = $dat[1];
	     $d3 = $dat[2];
	     $d4 = $dat[3];
	     echo "<tr> <td>overall</td>";
	     if($d0>$av1)
	       echo "<td bgcolor='#cc3333'>";
	     else
	       echo "<td bgcolor='#33cc33'>";
	     echo round($d0,2)."</td>";
	     if($d1>$av2)
	       echo "<td bgcolor='#cc3333'>";
	     else
	       echo "<td bgcolor='#33cc33'>";
	     echo round($d1,2)."</td><td> $d3 </td><td> $d4 </td></tr>\n";
	   }
	 echo "</tbody></table>\n";
	 echo "</div>\n";
       }
         
     /* games the player played in */
     echo "<div class=\"games\">\n";
     echo "<h4> the following games are in the database</h4>\n";
     echo "<table><thead><tr>\n";
     foreach($names as $name)
       {
	 echo "<th>$name</th>\n";
       };
     echo "</tr></thead>\n<tbody>\n<tr>\n";
     foreach($names as $name)
       {
	 echo "<td>\n";
	 $datatmp = mysql_query("SELECT session.date,".
				"       session.id ".
				"FROM scores LEFT JOIN players ON players.id=scores.player ".
				"            LEFT JOIN games   ON   games.id=scores.game ".
				"            LEFT JOIN session ON session.id=games.session ".
				"WHERE players.name=".DB_quote_smart($name)." ".
				"GROUP BY session.id ".
				"ORDER BY session.date");
	 
	 echo "<ul>\n";
	 while($dat =  mysql_fetch_array($datatmp, MYSQL_NUM))
	   {
	     $date=$dat[0];
	     $id=$dat[1];
	     echo "<li> <a href=\"index.php?games=$id\">$date</a> </li>\n";
	   }
	 echo "</ul></td>\n";
       }
     echo "</tr></tbody></table></div>\n";
     echo "<br class=\"clear\" />\n";
     echo "</div>\n";
     
   }
/*********************************
 *
 * Statistics for all players
 *
 *********************************/
 else if(isset($_REQUEST["total"]))
   {
     if ($_REQUEST["total"] == "games")
       {
	 echo "<div class=\"sorted-games\">\n";
	 echo "<h2> Scores </h2>\n";
	 echo "<table class=\"stats\" id=\"ScoreTable\">\n";
	 echo "<thead><tr><th>Name</th><th>#Games</th><th>Sum</th><th>Average</th><th>Sigma</th></tr></thead>\n";
	 echo "<tbody>\n";
	 $datatmp = mysql_query("SELECT players.id,".
				"       name,".
				"       sum(IF(score<0,0,score)),".
				"       avg(IF(score<0,0,score)),".
				"       count(*) as cnt, ".
				"       std(IF(score<0,0,score)) ".
				"FROM scores ".
				"   LEFT JOIN players ON players.id=scores.player ".
				"   LEFT JOIN games   ON   games.id=scores.game ".
				"   LEFT JOIN session ON session.id=games.session ".
				($groupsize?" WHERE session.number_of_players=".DB_quote_smart($groupsize)." ":"").
				"GROUP BY players.id ".
				"ORDER BY cnt DESC");
	 while($dat= mysql_fetch_array($datatmp, MYSQL_NUM))
	   {
	     $id = $dat[0];
	     $n  = $dat[1];
	     $s  = $dat[2];
	     $a  = $dat[3];
	     $N  = $dat[4];
	     $S  = $dat[5];
	     if ($N>$mingames)
	       echo "<tr><td><a href=\"index.php?name=".$n."\">$n</a></td> <td>$N</td><td>$s</td> <td>$a</td> <td>$S</td> </tr>\n";
	   }
	 echo "</tbody></table>\n</div>\n";
       }
     else if ($_REQUEST["total"] == "movingaverage")
       {
	 echo "<div class=\"sorted-moving\">\n";	
	 
	 /* get the number of players */
	 $maxid = mysql_query("SELECT count(id) FROM players ");
	 $maxid = mysql_fetch_array($maxid, MYSQL_NUM);
	 $maxid = $maxid[0];
	 
	 /* get the  last 50 games of each player */
	 $j=1;
	 if($mingames>50) $mingames=50;
	 for($i=1;$i<$maxid;$i++)
	   {
	     $datatmp = mysql_query( "SELECT IF(score<0,0,score) as scores, players.name ".
				     "FROM scores LEFT JOIN players ON players.id=scores.player ".
				     "            LEFT JOIN games   ON games.id=scores.game ".
				     "            LEFT JOIN session ON session.id=games.session ".
				     "WHERE scores.player=$i ".($groupsize?" AND session.number_of_players=".DB_quote_smart($groupsize)." ":"").
				     "ORDER BY session.date DESC, scores.id DESC ".
				     "LIMIT 50");
	     
	     $n=0;
	     $data[$j] = array();
	     while($score=mysql_fetch_array($datatmp, MYSQL_NUM))
	       {
		 $data[$j]['name']=$score[1];
		 $data[$j][] = $score[0];
		 $n++;
	       };


	     if($n>=$mingames && $n>0)
	       $j++;
	     else
	       unset($data[$j]);

	   };
	 $maxid=$j;

	 $datout = array(array(array()));
	 /* do the average for the last $k games */
	 for($k=50; $k>0;$k-=10)
	   {
	     for($i=1;$i<$maxid;$i++)
	       {
		 $N=0;
		 $sum=0;
		 
		 /* add up the points*/
		 foreach($data[$i] as $dat)
		   {
		     $s = $dat;
		     if ($s==-1) $s=0;
		     
		     $sum += $s;
		     $N++;
		     
		     if($N==$k) break;
		   };
		 
		 /* average and save result into table */
		 if($N==$k) 
		   { /* got enough data points*/
		     $datout[$k][$i]['sum'] = $sum;
		     $datout[$k][$i]['avg'] = $sum/$N;
		     $datout[$k][$i]['num'] = $N;
		   }
		 else
		   { /* not enough data points */
		     $datout[$k][$i]['sum'] = "";
		     $datout[$k][$i]['avg'] = "";
		     $datout[$k][$i]['num'] = 0;
		   };
	       };
	   };
	 
	 /* output sorted results */
	 echo "<h2>sorted by Moving Average</h2>";
	 echo "<table class=\"stats\" id=\"ScoreTable\">\n";
	 echo "<thead><tr><th>Name</th>";
	 for($k=50; $k>0;$k-=10)
	   {
	     echo "<th>$k-Average (Sum)</th>";
	   };
	 echo "</tr></thead>\n<tbody>";
	 
	 for($i=1;$i<$maxid;$i++)
	   {
	     $name = $data[$i]['name'];
	     
	     $output = "";
	     $output.= "<tr><td><a href=\"index.php?name=".$name."\">$name</a></td>";
	     
	     for($k=50; $k>0;$k-=10)
	       {
		 $s  = $datout[$k][$i]['sum'];
		 $a  = round($datout[$k][$i]['avg'],2);
		 
		 if ($datout[$k][$i]['num']>0)
		   $output.="<td>$a ($s)</td>";
		 else
		   $output.="<td>-</td> ";
	       }
	     $output .= "</tr>\n";
	     echo $output;
	   }
	 echo "</tbody></table>\n";
	 
	 echo "</div>\n";
       };
   }
/******************************
 *
 * check for games 
 *
 *********************************/
 else if(isset($_REQUEST["games"]))
   {
     /* list dates and locations of all the sessions */
     if($_REQUEST["games"]=='all')
       {
	 echo "<div class=\"games\">\n";
	 echo "<h2> All Games </h2>\n";
	 echo "<table>\n";
	 echo "<thead><tr><th>ID</th><th>Date</th><th>Where</th><th>Number of Players</th></tr></thead>\n";
	 echo "<tbody>\n";
	 $datatmp = mysql_query("SELECT * FROM session ".($groupsize?" WHERE session.number_of_players=".DB_quote_smart($groupsize)."":"")." ORDER BY date DESC");
	 while($dat= mysql_fetch_array($datatmp, MYSQL_NUM))
	   {
	     $id   = $dat[0]; /*id*/
	     $date = $dat[1]; /*date*/
	     $loc  = $dat[2]; /*location*/
	     $num  = $dat[3]; /*number of players*/
	     echo "<tr><td><a href=\"index.php?games=$id&amp;".$options."\">$id </a></td><td> $date</td><td>$loc</td><td>$num</td></tr>\n";
	   }
	 echo "</tbody>\n";
	 echo "</table>\n</div>\n";
       }
     else
       {
	 echo "<div class=\"games\">\n";
	 $id = $_REQUEST["games"];
	 $datatmp = mysql_query("SELECT * FROM session  WHERE id=".DB_quote_smart($id));
	 $data    = mysql_fetch_array($datatmp, MYSQL_NUM);
	 echo "<h2> Game ".$data[1]." ".$data[2]." </h2>\n";
	 echo "<table>\n";
	 
	 $points    = array(array());
	 $sumpoints = array();
	 $names     = array();
	 
	 $datatmp = mysql_query("SELECT  scores.score,".
				"        players.name,".
				"        games.end_with_black_card,".
				"        games.id ".
				"FROM scores LEFT JOIN games ON games.id=scores.game LEFT JOIN players ON scores.player=players.id ".
				"WHERE games.session=".DB_quote_smart($id));
	 while($dat= mysql_fetch_array($datatmp, MYSQL_NUM))
	   {
	     $score  = $dat[0]; /*score*/
	     $name   = $dat[1]; /*name*/
	     $black  = $dat[2]; /*end with black card?*/ 
	     $id     = $dat[3]; /*games id*/
	     $points[$id][$name] = $score;
	     $points[$id]["blackcard"] = $black;
	     $names[$name] = 1; /* just to keep track of the names */
	   }
	 
	 /* table header */
	 echo "<thead><tr>";
	 foreach($names as $name =>$num)
	   {	
	     echo "<th> <a href=\"index.php?name=".$name."\">".$name."</a> </th>";
	     $sumpoints[$name]=0;
	   };
	 echo "<th> </th></tr></thead>\n";
	 
	 foreach($points as $id => $point)
	   {
	     if(isset($_REQUEST["special"]) && $id==$_REQUEST["special"])
	       echo "<tr class=\"special\">";
	     else
	       echo "<tr>";
	     foreach($point as $name =>$entry)
	       {
		 if($name!="blackcard")
		   if($entry==-1)
		     echo "<td> - </td>";
		   else
		     {
		       $sumpoints[$name] = $sumpoints[$name] + $entry;
		       echo "<td>".$sumpoints[$name]."</td>";
		     }
	       };
	     if(isset($point["blackcard"]) && $point["blackcard"])
	       echo "<td> * </td>";
	     else
	       echo "<td> </td>";
	     echo "</tr>\n";
	   }
	 
	 echo "</table>\n</div>\n";
       }
   }
/***************************
 *
 * lowest scoring game
 *
 ****************************/
 else if(isset($_REQUEST["lowest"]))
   {
     echo "<div class=\"games\">";
     echo "<h2>Low scoring games</h2>";
     echo "<table>
  <thead><tr>
      <th>Points</th>
      <th>Date and Location</th>
      <th>Number of Players</th>
  </tr></thead>\n";
  
     $datatmp = mysql_query("SELECT avg(IF(score<0,0,score)) as avgscore,".
			    "       games.session, games.id ".
			    "FROM scores ".
			    "LEFT JOIN games ON scores.game=games.id ".
			    "LEFT JOIN session ON session.id=games.session ".
			    ($groupsize?" WHERE session.number_of_players=".DB_quote_smart($groupsize)." ":"").
			    "GROUP BY games.id  ".
			    "ORDER BY avgscore ".
			    "LIMIT 15"); 
     
     while($dat= mysql_fetch_array($datatmp, MYSQL_NUM))
       {
	 $low_sessionid = $dat[1];
	 $low_avgscore  = round($dat[0],3);
	 $games_id      = $dat[2];
	 /* get date and location */
	 $locationtmp = mysql_query("SELECT date, location, number_of_players FROM session WHERE session.id='$low_sessionid'");
	 while($tdat = mysql_fetch_array($locationtmp, MYSQL_NUM))
	   {
	     $low_date     = $tdat[0];
	     $low_location = $tdat[1];
	     $low_nop      = $tdat[2];
	   };
	 echo "  <tr>
    <td>$low_avgscore</td>
    <td><a href=\"index.php?games=$low_sessionid&amp;special=$games_id\">($low_date,$low_location)</a></td>
    <td>$low_nop</td>
  </tr>\n";
       };
     echo "</table>\n</div>\n";
   }
/******************************
 *
 * highest scoring game
 *
 *****************************/
 else if(isset($_REQUEST["highest"]))
   {
     echo "<div class=\"games\">";
     echo "<h2>High scoring games</h2>";
     echo "<table>
  <thead><tr>
      <th>Points</th>
      <th>Date and Location</th>
      <th>Number of Players</th>
  </tr></thead>\n";

     $datatmp = mysql_query("SELECT avg(IF(score<0,0,score)) as avgscore,".
			    "       games.session, games.id ".
			    "FROM scores LEFT JOIN games ON scores.game=games.id ".
			    "LEFT JOIN session ON session.id=games.session ".
			    ($groupsize?" WHERE session.number_of_players=".DB_quote_smart($groupsize)." ":"").
			    "GROUP BY games.id ".
			    "ORDER BY avgscore DESC ".
			    "LIMIT 15");
     while($dat= mysql_fetch_array($datatmp, MYSQL_NUM))
       {
	 $high_sessionid = $dat[1];
	 $high_avgscore  = round($dat[0],3);
	 $games_id       = $dat[2];
	 
	 $tdatatmp = mysql_query("SELECT date, location, number_of_players FROM session WHERE session.id='$high_sessionid'");
	 while($tdat= mysql_fetch_array($tdatatmp, MYSQL_NUM))
	   {
	     $high_date     = $tdat[0];
	     $high_location = $tdat[1];
	     $high_nop      = $tdat[2];
	   };
	 echo "  <tr>
    <td>$high_avgscore</td>
    <td><a href=\"index.php?games=$high_sessionid&amp;special=$games_id\">($high_date,$high_location)</a></td>
    <td>$high_nop</td>
  </tr>\n";
       };
     echo "</table>\n</div>\n";
   }
/****************************
 *
 * get some general statistics as a default case
 *
 ****************************/
 else
   {
     echo "<p> ";
     
     /* get average points */
     $datatmp = mysql_query("SELECT avg(IF(score<0,0,score)),count(*) FROM scores ");
     while($dat= mysql_fetch_array($datatmp, MYSQL_NUM))
       {
	 $scores  = $dat[1];
	 $average  = round($dat[0],2);
       };
     /* get average points for games that ended with a black card */
     $datatmp = mysql_query("SELECT avg(IF(score<0,0,score)),count(*) ".
			    "FROM scores LEFT JOIN games ON scores.game=games.id ".
			    "WHERE games.end_with_black_card='1'");
     while($dat= mysql_fetch_array($datatmp, MYSQL_NUM))
       {
	 $blackscores  = $dat[1];
	 $blackaverage  = round($dat[0],2);
       };
     /* get statistics about how many player are in a round */
     $datatmp = mysql_query("SELECT count(*),MIN(number_of_players),MAX(number_of_players), AVG(number_of_players) FROM session ");
     while($dat= mysql_fetch_array($datatmp, MYSQL_NUM))
       {
	 $session  = $dat[0];
	 $minpla = $dat[1];
	 $avgpla = round($dat[3],2);
	 $maxpla = $dat[2];
       };
     /* get lowest scoring game */
     $datatmp = mysql_query("SELECT avg(IF(score<0,0,score)) as avgscore,games.session,games.id ".
			    "FROM scores LEFT JOIN games ON scores.game=games.id ".
			    "GROUP BY games.id ".
			    "ORDER BY avgscore ".
			    "LIMIT 1");
     while($dat= mysql_fetch_array($datatmp, MYSQL_NUM))
       {
	 $low_sessionid = $dat[1];
	 $low_avgscore  = round($dat[0],3);
	 $low_games_id  = $dat[2];
       };
     $datatmp = mysql_query("SELECT date, location FROM session WHERE session.id='$low_sessionid'");
     while($dat= mysql_fetch_array($datatmp, MYSQL_NUM))
       {
	 $low_date = $dat[0];
	 $low_location = $dat[1];
       };
     /* highest */
     $datatmp = mysql_query("SELECT avg(IF(score<0,0,score))as avgscore,games.session,games.id ".
			    "FROM scores LEFT JOIN games ON scores.game=games.id ".
			    "GROUP BY games.id ".
			    "ORDER BY avgscore DESC ".
			    "LIMIT 1");
     while($dat= mysql_fetch_array($datatmp, MYSQL_NUM))
       {
	 $high_sessionid = $dat[1];
	 $high_avgscore  = round($dat[0],3);
	 $high_games_id  = $dat[2];
       };
     $datatmp = mysql_query("SELECT date, location FROM session WHERE session.id='$high_sessionid'");
     while($dat= mysql_fetch_array($datatmp, MYSQL_NUM))
       {
	 $high_date = $dat[0];
	 $high_location = $dat[1];
       };
     
     /*output*/
     echo "
  The database consists of $session sessions. <br />
  The average score per game is $average (".round($blackscores/$scores*100,1)."% 
  of the games ended with a black card; average for those games ".
       round($blackaverage,2)."). <br />

  A total of $scores scores are stored in the database. <br />

  The smallest round of uno consists of $minpla players, the biggest one 
  had $maxpla players, the average  is $avgpla.<br /> 

  <a href=\"index.php?lowest=1\">lowest scoring game</a> 
  ever: $low_avgscore <a href=\"index.php?games=$low_sessionid&amp;special=$low_games_id\">($low_date,$low_location)</a><br />

  <a href=\"index.php?highest=1\">highest scoring game</a> ever: $high_avgscore 
  <a href=\"index.php?games=$high_sessionid&amp;special=$high_games_id\">($high_date,$high_location)</a>
  </p>
   ";
     
   }

mysql_close($db);
?>
</div>
</body>
</html>